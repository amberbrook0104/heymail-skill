"""Shared local application ledger. No SMTP, IMAP, or credential access."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email.utils import getaddresses
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid
import xml.etree.ElementTree as ET
import zipfile
import sys
from xml.sax.saxutils import escape

HEADERS = ["公司", "岗位", "工作地点", "投递时间", "投递 Agent", "收件邮箱", "当前进展", "最新进展", "备注", "_record_id"]
# Retain the historical storage key so existing private state remains compatible.
MANUAL = ("company", "position", "location", "progress", "follow_up", "notes")
STATES = {"accepted": "已投递", "rejected": "投递失败", "uncertain": "发送待核实", "submitting": "发送待核实"}
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path, default=None):
    return json.loads(Path(path).read_text(encoding="utf-8-sig")) if Path(path).exists() else default


def agent_name(script_path):
    path = str(script_path).lower()
    if "doubao" in path:
        return "豆包"
    if "workbuddy" in path:
        return "WorkBuddy"
    if ".codex" in path:
        return "Codex"
    return "其他"


def normalize_city(value):
    value=str(value or '').strip()
    value=re.sub(r'^(?:base|地点|工作地点|地址)\s*[:：]?\s*','',value,flags=re.I)
    if not value or value=='待确认':return value
    if value in ('远程','线上','居家','remote','Remote'):return '远程'
    if re.fullmatch(r'(?:可|支持|完全)?(?:远程|线上|居家)(?:实习|办公|工作)?',value):return '远程'
    parts=re.split(r'[/、,，;；|]',value)
    if len(parts)>1:
        cities=list(dict.fromkeys(normalize_city(part) for part in parts if part.strip()))
        return '/'.join(city for city in cities if city) or '待确认'
    common='北京 上海 天津 重庆 香港 澳门 深圳 广州 杭州 成都 南京 武汉 西安 苏州 宁波 合肥 郑州 长沙 青岛 济南 厦门 福州 无锡 佛山 东莞 珠海 大连 沈阳 长春 哈尔滨 昆明 贵阳 南宁 海口 石家庄 太原 兰州 银川 西宁 乌鲁木齐 呼和浩特 拉萨 南昌 温州 泉州 常州 南通 嘉兴 绍兴 扬州 烟台 洛阳 唐山 保定 惠州 中山'.split()
    for city in common:
        if value.startswith(city):return city
    locality=re.sub(r'^.+?(?:省|自治区)','',value)
    match=re.match(r'([\u4e00-\u9fff]{2,12}?)市',locality)
    if match:return match.group(1)
    if re.search(r'路|街|大道|栋|号|园区|大厦|区|县',value) or len(value)>20:return '待确认'
    return value


def normalize_application(data):
    if data is None:
        return {}
    allowed = {"id", "company", "position", "location", "jd_source", "jd_text", "notes"}
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError("invalid_application_fields")
    result = {}
    for key, value in data.items():
        if not isinstance(value, str) or len(value) > (60000 if key == "jd_text" else 2000):
            raise ValueError("invalid_application_value")
        result[key] = value.strip()
    if 'location' in result:result['location']=normalize_city(result['location'])
    if result.get("id") and not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", result["id"]):
        raise ValueError("invalid_application_id")
    return result


def application_id(application, manifest):
    if application.get("id"):
        return application["id"]
    key = [application.get(k, "") for k in ("company", "position", "location", "jd_source", "jd_text")]
    if not any(key):
        key = [manifest.get("to", ""), manifest.get("subject", "")]
    return hashlib.sha256(json.dumps(key, ensure_ascii=False).encode()).hexdigest()[:32]


def local_time(value):
    value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None).isoformat(timespec="seconds")


def document_author(settings):
    author = settings.get("author")
    if not author:
        branding = read_json(Path(settings["root"]) / ".branding.json", {})
        author = branding.get("author")
    return author.strip() if isinstance(author, str) and author.strip() else "User"


def archive_source(root, identifier, application, manifest, author="User"):
    folder = root / "JD来源"
    folder.mkdir(exist_ok=True)
    source = application.get("jd_source", "")
    if source.startswith(("https://", "http://")):
        return {"label": "招聘链接", "target": source}
    if source and Path(source).is_file():
        original = Path(source)
        dest = folder / (identifier + original.suffix.lower())
        if original.resolve() != dest.resolve():
            shutil.copy2(original, dest)
        return {"label": "JD截图" if original.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") else "JD材料", "target": str(dest)}
    text = application.get("jd_text", "")
    label = "JD文字" if text else "邮件记录（JD待补）"
    dest = folder / (identifier + ".md")
    if text:
        content = text
    else:
        content = "未找到原始JD，本文件保留实际发送内容供核对。\n\n主题：" + manifest.get("subject", "") + "\n\n" + manifest.get("body", "")
    dest.write_text("作者：" + author + "\n\n" + content + "\n", encoding="utf-8")
    return {"label": label, "target": str(dest)}


def record_event(settings, manifest, receipt, receipt_path, agent=None, application=None, archive=True):
    root = Path(settings["root"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    application = normalize_application(application if application is not None else manifest.get("application", {}))
    identifier = application_id(application, manifest)
    message_key = receipt.get("message_id") or "|".join(str(receipt.get(k, "")) for k in ("digest", "to", "time"))
    event_id = hashlib.sha256(message_key.encode()).hexdigest()
    event = {"event_id": event_id, "application_id": identifier,
             "application": {k: application.get(k, "") for k in ("company", "position", "location", "notes")},
             "agent": agent or manifest.get("agent") or "其他",
             "time": local_time(receipt["time"]), "status": receipt["status"],
             "recipient": receipt.get("to", manifest.get("to", "")),
             "message_id": receipt.get("message_id", ""),
             "receipt_path": str(Path(receipt_path).resolve()),
             "source": archive_source(root, identifier, application, manifest, document_author(settings)) if archive else None}
    atomic_json(root / ".events" / (event_id + ".json"), event)
    return event


def read_workbook_rows(path):
    """Read only user-entered cells and stable row IDs using XLSX XML."""
    if not path.exists():
        return {}
    with zipfile.ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            for item in ET.fromstring(archive.read("xl/sharedStrings.xml")):
                strings.append("".join(item.itertext()))
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        headers = {}
        for row in sheet.findall("s:sheetData/s:row", NS):
            labels = {}
            for cell in row.findall("s:c", NS):
                col = re.match(r"[A-Z]+", cell.attrib["r"]).group()
                value = cell.find("s:v", NS)
                if cell.attrib.get("t") == "s" and value is not None:
                    labels[col] = strings[int(value.text)]
                elif cell.attrib.get("t") == "inlineStr":
                    labels[col] = "".join(cell.find("s:is", NS).itertext())
                elif value is not None:
                    labels[col] = value.text
            if labels.get("A") == "公司" and labels.get("B") == "岗位":
                headers = {label: col for col, label in labels.items()}
                break
        source_column = headers.get("JD来源")
        notes_column = headers.get("备注", "I")
        id_column = headers.get("_record_id", "J")
        recipient_column = headers.get("收件邮箱")
        latest_column = headers.get("最新进展", headers.get("下次跟进", "G"))
        relationships = {}
        rel_path = "xl/worksheets/_rels/sheet1.xml.rels"
        if rel_path in archive.namelist():
            relationships = {r.attrib["Id"]: r.attrib.get("Target", "") for r in ET.fromstring(archive.read(rel_path))}
        links = {h.attrib["ref"]: relationships.get(h.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"), "")
                 for h in sheet.findall("s:hyperlinks/s:hyperlink", NS)}
        result = {}
        for row in sheet.findall("s:sheetData/s:row", NS):
            cells = {}
            for cell in row.findall("s:c", NS):
                col = re.match(r"[A-Z]+", cell.attrib["r"]).group()
                f, v = cell.find("s:f", NS), cell.find("s:v", NS)
                if f is not None and col == source_column:
                    match = re.fullmatch(r'HYPERLINK\("((?:[^"]|"")*)","((?:[^"]|"")*)"\)', f.text or "", re.I)
                    value = {"label": match.group(2).replace('""', '"'), "target": match.group(1).replace('""', '"')} if match else {"formula": "=" + (f.text or "")}
                elif f is not None:
                    value = {"formula": "=" + (f.text or "")}
                elif cell.attrib.get("t") == "inlineStr":
                    value = "".join(cell.find("s:is", NS).itertext())
                elif cell.attrib.get("t") == "s":
                    value = strings[int(v.text)] if v is not None else ""
                elif v is None:
                    value = None
                elif cell.attrib.get("t") in ("str", "e"):
                    value = v.text or ""
                else:
                    try:
                        value = float(v.text)
                    except (TypeError, ValueError):
                        value = v.text
                if col == source_column and not isinstance(value, dict):
                    value = {"label": value or "待补充", "target": links.get(cell.attrib["r"], "")}
                cells[col] = value
            if cells.get("A") == "公司" or not (cells.get("A") or cells.get("B")):
                continue
            # Keep stable semantic slots for both the old and new physical layouts.
            physical = cells
            semantic_headers = {"A": "公司", "B": "岗位", "C": "工作地点", "D": "投递时间",
                                "E": "投递 Agent", "F": "当前进展"}
            cells = {col: physical.get(headers.get(label, col)) for col, label in semantic_headers.items()}
            cells["G"] = latest_progress_text(physical.get(latest_column), legacy_date="最新进展" not in headers)
            cells.update(H=physical.get(source_column) if source_column else None,
                         I=physical.get(notes_column), J=physical.get(id_column),
                         K=physical.get(recipient_column) if recipient_column else None)
            if not cells.get("J"):
                if int(row.attrib["r"]) < 5:
                    continue
                identity = {key: value for key, value in cells.items() if key != "K"}
                cells["J"] = "manual_" + hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
            result[str(cells["J"])] = cells
        return result


def latest_progress_text(value, legacy_date=False):
    if value is None or value == "":
        return None
    if isinstance(value, dict) and value.get("formula"):
        return "原有公式：" + value["formula"]
    if isinstance(value, (int, float)) and legacy_date:
        return (datetime(1899, 12, 30) + timedelta(days=value)).strftime("%Y-%m-%d")
    return str(value)


def recipient_emails(events):
    """Keep actual submission addresses in first-use order, without duplicates."""
    addresses, seen = [], set()
    for event in events:
        value = event.get("recipient")
        values = value if isinstance(value, list) else [value]
        for _, address in getaddresses([line for v in values if isinstance(v,str) for line in v.splitlines() if line.strip()]):
            address = address.strip()
            if "@" in address and address.casefold() not in seen:
                seen.add(address.casefold())
                addresses.append(address)
    return "\n".join(addresses)


def aggregate(events):
    groups = {}
    for event in events:
        groups.setdefault(event["application_id"], []).append(event)
    rows = []
    for identifier, group in groups.items():
        group.sort(key=lambda item: item["time"])
        accepted = [e for e in group if e["status"] == "accepted"]
        base = (accepted or group)[0]
        latest = group[-1]
        metadata = next((e["application"] for e in reversed(group) if e["application"].get("company")), base["application"])
        notes = metadata.get("notes", "")
        if len(accepted) > 1:
            additions = "；".join(e["time"].replace("T", " ")[:16] + "（" + e["agent"] + "）" for e in accepted[1:])
            notes = (notes + "；" if notes else "") + "追加投递：" + additions
        rows.append({"id": identifier, "company": metadata.get("company") or "待确认",
                     "position": metadata.get("position") or "待确认", "location": metadata.get("location") or "待确认",
                     "time": base["time"], "agent": "、".join(sorted({e["agent"] for e in group})),
                     "recipients": recipient_emails(group),
                     "progress": "已投递" if accepted else STATES.get(latest["status"], "发送待核实"),
                     "follow_up": None, "source": next((e["source"] for e in reversed(group) if e.get("source")), None),
                     "notes": notes})
        source = rows[-1].get("source")
        if source and source.get("target") and not source["target"].startswith(("http://", "https://", "file:")):
            source = dict(source)
            source["target"] = Path(source["target"]).resolve().as_uri()
            rows[-1]["source"] = source
    return sorted(rows, key=lambda r: time_sort_key(r.get("time")), reverse=True)


def time_sort_key(value):
    if isinstance(value, (int, float)):
        return (datetime(1899, 12, 30) + timedelta(days=value)).isoformat()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None).isoformat()
        except ValueError:
            return ""
    return ""


def list_applications(settings, query=""):
    root = Path(settings["root"])
    events = [read_json(p) for p in (root / ".events").glob("*.json")]
    state = read_json(root / ".state.json", {})
    result = []
    for row in aggregate(events):
        row.update(state.get("overrides", {}).get(row["id"], {}))
        if query and query.casefold() not in ((row.get("company") or "") + " " + (row.get("position") or "")).casefold():
            continue
        result.append({k: row.get(k) for k in ("id", "company", "position", "location", "agent", "progress")})
    return result


@contextmanager
def sync_lock(root):
    path = root / ".sync.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
        yield
    finally:
        path.unlink(missing_ok=True)


def finalize_xlsx(path, rows, author="User"):
    """Set author and hide stable IDs while retaining the writer's other parts."""
    with zipfile.ZipFile(path) as z:
        data = {n: z.read(n) for n in z.namelist()}
    data['docProps/core.xml'] = ('<?xml version="1.0" encoding="utf-8"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>' + escape(author) + '</dc:creator>'
        '<cp:lastModifiedBy>' + escape(author) + '</cp:lastModifiedBy></cp:coreProperties>').encode('utf-8')
    content_types = data['[Content_Types].xml'].decode('utf-8')
    if '/docProps/core.xml' not in content_types:
        content_types = content_types.replace('</Types>', '<Override PartName="/docProps/core.xml" '
            'ContentType="application/vnd.openxmlformats-package.core-properties+xml" /></Types>')
    data['[Content_Types].xml'] = content_types.encode('utf-8')
    package_rels = data['_rels/.rels'].decode('utf-8')
    if '/metadata/core-properties' not in package_rels:
        package_rels = package_rels.replace('</Relationships>', '<Relationship Id="heymailCore" '
            'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
            'Target="/docProps/core.xml" /></Relationships>')
    data['_rels/.rels'] = package_rels.encode('utf-8')
    worksheet = data["xl/worksheets/sheet1.xml"].decode("utf-8")
    prefix = re.search(r'<([A-Za-z0-9]+):worksheet\b', worksheet).group(1) + ':'
    id_column_number = len(HEADERS)
    pattern = r'<' + prefix + r'col\b(?=[^>]*\bmin="' + str(id_column_number) + r'")(?=[^>]*\bmax="' + str(id_column_number) + r'")[^>]*/>'
    def hide(match):
        text = match.group(0)
        return re.sub(r'hidden="[01]"', 'hidden="1"', text) if 'hidden=' in text else text[:-2] + ' hidden="1" />'
    worksheet, count = re.subn(pattern, hide, worksheet)
    if count != 1:
        raise ValueError("stable_id_column_not_found")
    data["xl/worksheets/sheet1.xml"] = worksheet.encode("utf-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, value in data.items():
            z.writestr(name, value)


def sync(settings, render=False, new_record=None):
    root = Path(settings["root"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    workbook = Path(settings.get('workbook') or root / "实习投递台账.xlsx").resolve()
    if workbook.parent != root or workbook.suffix.lower()!='.xlsx':
        raise ValueError('workbook_must_be_xlsx_in_ledger_root')
    with sync_lock(root):
        state_path = root / ".state.json"
        state = read_json(state_path, {"overrides": {}, "last_export": {}, "manual_rows": {}})
        events = [read_json(p) for p in (root / ".events").glob("*.json")]
        event_ids={event['application_id'] for event in events}
        existing = read_workbook_rows(workbook)
        for identifier, cells in existing.items():
            if identifier.startswith("manual_") or identifier not in event_ids:
                state["manual_rows"][identifier] = cells
            previous = state["last_export"].get(identifier, {})
            for field, col in (("company", "A"), ("position", "B"), ("location", "C"),
                               ("progress", "F"), ("follow_up", "G"), ("notes", "I")):
                value = cells.get(col)
                if value == "":
                    value = None
                if field not in previous or value != previous[field]:
                    state["overrides"].setdefault(identifier, {})[field] = value
        atomic_json(state_path, state)
        if new_record is not None:
            permitted={'id','company','position','location','time','agent','recipients','progress','latest_progress','notes'}
            if not isinstance(new_record,dict) or set(new_record)-permitted:
                raise ValueError('invalid_ledger_record_fields')
            if any(not isinstance(value,str) or len(value)>2000 for value in new_record.values()):
                raise ValueError('ledger_record_values_must_be_short_strings')
            if not new_record.get('company') or not new_record.get('position'):
                raise ValueError('company_and_position_required')
            identifier=new_record.get('id') or 'manual_'+uuid.uuid4().hex
            if not re.fullmatch(r'manual_[A-Za-z0-9_-]{1,100}',identifier):
                raise ValueError('standalone_record_id_must_start_with_manual_')
            if identifier in existing or identifier in state['manual_rows']:
                raise ValueError('record_id_already_exists')
            timestamp=new_record.get('time') or datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None).isoformat(timespec='seconds')
            if not time_sort_key(timestamp):raise ValueError('invalid_record_time')
            state['manual_rows'][identifier]={'A':new_record['company'],'B':new_record['position'],
                'C':new_record.get('location') or '待确认','D':timestamp,'E':new_record.get('agent') or '其他',
                'F':new_record.get('progress') or '待确认','G':new_record.get('latest_progress'),
                'H':None,'I':new_record.get('notes'),'J':identifier,'K':new_record.get('recipients')}
            atomic_json(state_path,state)
        rows = aggregate(events)
        for identifier, cells in state["manual_rows"].items():
            if identifier in event_ids:continue
            rows.append({"id": identifier, "company": cells.get("A"), "position": cells.get("B"),
                         "location": cells.get("C"), "time": cells.get("D"), "agent": cells.get("E"),
                         "progress": cells.get("F"), "follow_up": latest_progress_text(cells.get("G"), legacy_date=True),
                         "recipients": cells.get("K") or "",
                         "source": cells.get("H") or {"label": "待补充", "target": ""}, "notes": cells.get("I")})
        for row in rows:
            row.update(state["overrides"].get(row["id"], {}))
        rows.sort(key=lambda row: time_sort_key(row.get("time")), reverse=True)
        payload = root / ".export.json"
        atomic_json(payload, {"rows": rows, "headers": HEADERS, "render": render})
        temporary = root / (".export-" + uuid.uuid4().hex + ".xlsx")
        try:
            from importlib.util import spec_from_file_location, module_from_spec
            spec = spec_from_file_location('heymail_excel', Path(__file__).with_name('tracker_excel.py'))
            exporter = module_from_spec(spec)
            spec.loader.exec_module(exporter)
            exporter.export(rows, temporary, document_author(settings))
            os.replace(temporary, workbook)
        finally:
            temporary.unlink(missing_ok=True)
            Path(str(temporary) + '.inspect.ndjson').unlink(missing_ok=True)
        state["last_export"] = {row["id"]: {field: (None if row.get(field) == "" else row.get(field)) for field in MANUAL} for row in rows}
        atomic_json(state_path, state)
        return {"workbook": str(workbook), "rows": len(rows), "events": len(events)}


def write_excel_rows(settings, root, workbook, rows):
    rows.sort(key=lambda row:time_sort_key(row.get('time')),reverse=True)
    temporary=root/('.append-'+uuid.uuid4().hex+'.xlsx')
    try:
        from importlib.util import spec_from_file_location,module_from_spec
        spec=spec_from_file_location('heymail_excel',Path(__file__).with_name('tracker_excel.py'))
        exporter=module_from_spec(spec);spec.loader.exec_module(exporter)
        exporter.export(rows,temporary,document_author(settings));os.replace(temporary,workbook)
    finally:temporary.unlink(missing_ok=True)
    return {'workbook':str(workbook),'rows':len(rows),'mode':'current_receipt_only'}


def append_event(settings, event=None):
    """Project the current receipt into Excel; never scan prior events or state."""
    root=Path(settings['root']).resolve();root.mkdir(parents=True,exist_ok=True)
    workbook=Path(settings.get('workbook') or root/'实习投递台账.xlsx').resolve()
    if workbook.parent!=root or workbook.suffix.lower()!='.xlsx':raise ValueError('invalid_workbook_path')
    with sync_lock(root):
        rows=[]
        for identifier,cells in read_workbook_rows(workbook).items():
            rows.append({'id':identifier,'company':cells.get('A'),'position':cells.get('B'),
                'location':normalize_city(cells.get('C')),'time':cells.get('D'),'agent':cells.get('E'),
                'progress':cells.get('F'),'follow_up':cells.get('G'),'notes':cells.get('I'),
                'recipients':cells.get('K') or ''})
        if event is None:return write_excel_rows(settings,root,workbook,rows)
        incoming=aggregate([event])[0];incoming['location']=normalize_city(incoming.get('location'))
        if event.get('status')=='manual_entry':
            incoming['progress']=event.get('progress') or '待确认'
            incoming['follow_up']=event.get('latest_progress')
        existing=next((row for row in rows if row['id']==incoming['id']),None)
        if existing is not None and event.get('status')=='manual_entry':raise ValueError('record_id_already_exists')
        if existing is None:rows.append(incoming)
        else:
            for key in ('company','position','location'):
                if not existing.get(key) or existing[key]=='待确认':existing[key]=incoming[key]
            existing['agent']='、'.join(sorted(set(filter(None,(existing.get('agent') or '').split('、')+[event['agent']]))))
            existing['recipients']=recipient_emails([{'recipient':(existing.get('recipients') or '').splitlines()},event])
            if not existing.get('progress') or existing['progress'] in ('投递失败','发送待核实'):
                existing['progress']=incoming['progress']
            if time_sort_key(existing.get('time'))[:19]!=time_sort_key(event['time'])[:19]:
                addition='追加投递：'+event['time'].replace('T',' ')[:16]+'（'+event['agent']+'）'
                old=existing.get('notes') or ''
                if isinstance(old,str) and addition not in old:existing['notes']=old+('；' if old else '')+addition
        return write_excel_rows(settings,root,workbook,rows)


def record_submission(config, manifest, receipt, receipt_path, script_path):
    settings = config.get("tracker")
    if not settings:
        return None
    settings = {**settings, "author": config["display_name"]}
    event=record_event(settings, manifest, receipt, receipt_path, agent=manifest.get("agent") or agent_name(script_path),archive=False)
    try:
        return {"ok": True, **append_event(settings,event)}
    except Exception as error:
        return {"ok": False, "recorded": True, "refresh_pending": True,
                "error_type": type(error).__name__, "note": "邮件记录已保存，Excel待刷新；不要重发邮件"}


def create_desktop_shortcut(settings, desktop=None):
    workbook = Path(settings.get('workbook') or Path(settings["root"]).resolve() / "实习投递台账.xlsx")
    if not workbook.is_file():
        raise FileNotFoundError("tracker_workbook_not_found_run_tracker_sync_first")
    if os.name != "nt":
        raise OSError("desktop_shortcut_requires_windows")
    command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               str(Path(__file__).with_name("tracker-shortcut.ps1")), "-Workbook", str(workbook)]
    if desktop is not None:
        command += ["-DesktopDirectory", str(Path(desktop).resolve())]
    result = subprocess.run(command, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError("desktop_shortcut_creation_failed")
    return json.loads(result.stdout.decode("utf-8-sig"))


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Independent Excel ledger: no mailbox, credentials, Node or third-party packages.')
    parser.add_argument('command',choices=['init','sync','add','list','shortcut','rebuild'])
    parser.add_argument('--workbook',type=Path,required=True)
    parser.add_argument('--record',type=Path)
    parser.add_argument('--agent',default='其他')
    parser.add_argument('--author',default='User')
    args=parser.parse_args();book=args.workbook.resolve()
    settings={'root':str(book.parent),'workbook':str(book),'author':args.author}
    if args.command=='add':
        if args.record is None:parser.error('add requires --record')
        record=read_json(args.record)
        if not isinstance(record,dict):raise ValueError('record_must_be_object')
        allowed={'id','company','position','location','time','agent','recipients','progress','latest_progress','notes'}
        if set(record)-allowed or any(not isinstance(v,str) or len(v)>2000 for v in record.values()):raise ValueError('invalid_ledger_record_fields')
        if not record.get('company') or not record.get('position'):raise ValueError('company_and_position_required')
        identifier=record.get('id') or 'manual_'+uuid.uuid4().hex
        if not re.fullmatch(r'manual_[A-Za-z0-9_-]{1,100}',identifier):raise ValueError('standalone_record_id_must_start_with_manual_')
        timestamp=record.get('time') or datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None).isoformat(timespec='seconds')
        if not time_sort_key(timestamp):raise ValueError('invalid_record_time')
        event={'application_id':identifier,'application':{k:record.get(k,'') for k in ('company','position','location','notes')},
            'time':timestamp,'status':'manual_entry','agent':args.agent,'recipient':record.get('recipients',''),
            'progress':record.get('progress'),'latest_progress':record.get('latest_progress')}
        result=append_event(settings,event)
    elif args.command in ('sync','init'):result=append_event(settings)
    elif args.command=='rebuild':result=sync(settings)
    elif args.command=='shortcut':result=create_desktop_shortcut(settings)
    else:result={'rows':read_workbook_rows(book)}
    print(json.dumps({'ok':True,**result},ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'ok':False,'error_type':type(error).__name__,'detail':str(error)},ensure_ascii=False))
        sys.exit(1)
