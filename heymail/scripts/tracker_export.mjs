import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';

const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, all) => {
  if (v.startsWith('--')) a.push([v.slice(2), all[i + 1]]); return a;
}, []));
const require = createRequire(path.join(args.modules, 'package.json'));
const { Workbook, SpreadsheetFile, FileBlob } = await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
if (args['render-book']) {
 const book=await SpreadsheetFile.importXlsx(await FileBlob.load(args['render-book']));
 for (const [label,range] of [['top','A1:H16'],['middle','A17:H31'],['bottom','A32:H45']]) {
  const preview=await book.render({sheetName:'投递台账',range,scale:1.1,format:'png'});
  await fs.writeFile(path.join(args['preview-dir'],`ledger-${label}.png`),new Uint8Array(await preview.arrayBuffer()));
 }
 console.log(JSON.stringify({rendered:true,sheets:1}));
 process.exit(0);
}
const input = JSON.parse(await fs.readFile(args.input, 'utf8'));
let branding=null;
let brandingRoot=path.dirname(args.input);
try { branding=JSON.parse(await fs.readFile(path.join(brandingRoot,'.branding.json'),'utf8')); }
catch(error) {
 if(error.code!=='ENOENT') throw error;
 brandingRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../assets/ucass');
 try { branding=JSON.parse(await fs.readFile(path.join(brandingRoot,'theme.json'),'utf8')); }
 catch(packagedError) { if(packagedError.code!=='ENOENT') throw packagedError; }
}
if(args['check-branding']) {
 if(!branding) throw new Error('Branding settings unavailable.');
 const logo=await fs.readFile(path.resolve(brandingRoot,branding.logo));
 const motto=await fs.readFile(path.resolve(brandingRoot,branding.motto));
 if(logo.subarray(0,8).toString('hex')!=='89504e470d0a1a0a'||motto.subarray(0,2).toString('hex')!=='ffd8') throw new Error('Invalid branding images.');
 console.log(JSON.stringify({name:branding.name,packaged:brandingRoot.includes(path.join('assets','ucass')),logoBytes:logo.length,mottoBytes:motto.length}));
 process.exit(0);
}
const campus=branding?.name==='UCASS';
const palette=campus ? {accent:'#B81C22',ink:'#2C2525',muted:'#786B68',rule:'#E8DED9',stripe:'#FBF8F5',input:'#FFFDF9'}
                     : {accent:'#243A53',ink:'#233143',muted:'#667488',rule:'#DCE3EA',stripe:'#FFFFFF',input:'#FFF4D8'};
const wb = Workbook.create();
if (args.help) {
  console.log(wb.help('range.hyperlink',{include:'index,examples,notes',maxChars:2800}).ndjson);
  process.exit(0);
}
const sheet = wb.worksheets.add('投递台账');
sheet.showGridLines = false;
sheet.tabColor = palette.accent;
sheet.getRange('A1:H3').format.fill='#FFFFFF';
sheet.getRange('A1:H1').format.rowHeight=campus?8:15;
sheet.getRange('A2:H2').format.rowHeight=campus?34:22;
sheet.getRange('A3:H3').format.rowHeight=campus?22:15;
sheet.getRange(campus?'D2':'A2').values = [['实习投递台账']];
sheet.getRange(campus?'D2':'A2').format.font = {name:'Microsoft YaHei',size:16,bold:true,color:palette.accent};
sheet.getRange(campus?'D2':'A2').format.verticalAlignment='center';
sheet.getRange('A3:H3').format.borders = {bottom:{style:'thin',color:campus?'#C94D52':'#B7C5D3'}};
if(campus) {
 sheet.getRange('D3').format.font={name:'Microsoft YaHei',size:10,color:palette.muted};
 sheet.getRange('D3').format.verticalAlignment='center';
 const logo=await fs.readFile(path.resolve(brandingRoot,branding.logo));
 const motto=await fs.readFile(path.resolve(brandingRoot,branding.motto));
 sheet.images.add({dataUrl:'data:image/png;base64,'+logo.toString('base64'),anchor:{from:{row:1,col:0,colOffsetPx:2},extent:{widthPx:270,heightPx:270*150/581}}});
 sheet.images.add({dataUrl:'data:image/jpeg;base64,'+motto.toString('base64'),anchor:{from:{row:1,col:6,colOffsetPx:100,rowOffsetPx:8},extent:{widthPx:280,heightPx:280*423/3486}}});
}
const excelDate = value => {
  if (value == null || value === '') return null;
  if (typeof value === 'number' || typeof value === 'object') return value;
  const date = new Date(value.endsWith('Z') ? value : value.replace(' ', 'T') + 'Z');
  return Number.isNaN(date.getTime()) ? value : date;
};
const matrix = input.rows.map(row => [row.company,row.position,row.location,excelDate(row.time),row.agent,
  row.progress,excelDate(row.follow_up),row.notes || null,row.id]);
sheet.getRange('A4:I4').values = [input.headers];
if (matrix.length) sheet.getRange(`A5:I${matrix.length + 4}`).values = matrix.map(row => row.map(v =>
  v && typeof v === 'object' && !(v instanceof Date) ? null : v));
const end = Math.max(matrix.length + 4, 5);
sheet.getRange(`A4:I${end}`).format.font = {name:'Microsoft YaHei',size:10,color:palette.ink};
sheet.getRange(`A4:I${end}`).format.verticalAlignment = 'center';
sheet.getRange('A4:I4').format = {fill:palette.accent,font:{name:'Microsoft YaHei',size:10,bold:true,color:'#FFFFFF'},
  horizontalAlignment:'center',verticalAlignment:'center',rowHeight:campus?25:29};
sheet.getRange(`A5:I${end}`).format.rowHeight = campus?22:38;
sheet.getRange(`A5:C${end}`).format.wrapText = true;
sheet.getRange(`H5:H${end}`).format.wrapText = true;
const widths = campus?{A:23,B:27,C:10,D:21,E:13,F:11,G:14,H:43,I:14}
                     :{A:22,B:30,C:13,D:23,E:16,F:15,G:17,H:58,I:14};
for (const [col,width] of Object.entries(widths)) sheet.getRange(`${col}4:${col}${end}`).format.columnWidth=width;
sheet.getRange(`D5:D${end}`).setNumberFormat('yyyy-mm-dd hh:mm');
sheet.getRange(`D5:E${end}`).format.horizontalAlignment='center';
sheet.getRange(`C5:C${end}`).format.horizontalAlignment='center';
sheet.getRange(`F5:G${end}`).format.horizontalAlignment='center';
sheet.getRange(`G5:G${end}`).setNumberFormat('yyyy-mm-dd');
sheet.getRange(`F5:G${end}`).format.fill = palette.input;
sheet.getRange(`H5:H${end}`).format.fill = campus?'#FFFDF9':'#FFF9EC';
if(campus) {
 sheet.getRange(`E5:E${end}`).format.font={name:'Microsoft YaHei',size:10,color:palette.muted};
 sheet.getRange(`H5:H${end}`).format.font={name:'Microsoft YaHei',size:10,color:palette.muted};
}
sheet.getRange(`F5:F${Math.max(end,200)}`).dataValidation = {rule:{type:'list',values:
  ['已投递','已回复','面试中','已录用','未通过','已放弃','投递失败','发送待核实']}};
for (const [label,color] of [['已投递',campus?'#F4EEEC':'#EAF0F7'],['已回复','#E7F2FF'],['面试中','#FFF0C9'],['已录用','#DEF3E5'],['未通过','#FCE7E7'],['已放弃','#ECEFF2']]) {
  sheet.getRange(`F5:F${Math.max(end,200)}`).conditionalFormats.add('cellIs',{operator:'equal',formula:`"${label}"`,format:{fill:color}});
}
sheet.getRange(`G5:G${Math.max(end,200)}`).conditionalFormats.addCustom(
  'AND(ISNUMBER(G5),G5<=TODAY(),$F5<>"已录用",$F5<>"未通过",$F5<>"已放弃")',
  {fill:'#FBE0D9',font:{color:'#9B2C20',bold:true}});
for (let i=0;i<input.rows.length;i++) {
  const row=input.rows[i], r=i+5;
  if (row.follow_up && typeof row.follow_up==='object' && row.follow_up.formula)
    sheet.getRange(`G${r}`).formulas=[[row.follow_up.formula]];
}
const table=sheet.tables.add(`A4:I${end}`,true,'ApplicationsTable');
table.style=campus?'TableStyleLight1':'TableStyleLight9';
table.showFilterButton=true;
const visualLength=text=>Array.from(text||'').reduce((n,c)=>n+(c.charCodeAt(0)>255?2:1),0);
for(let i=0;i<input.rows.length;i++) {
 const row=input.rows[i];
 const lines=Math.max(Math.ceil(visualLength(row.company)/widths.A),Math.ceil(visualLength(row.position)/widths.B),Math.ceil(visualLength(row.notes)/widths.H));
 const r=i+5;
 const rowRange=sheet.getRange(`A${r}:I${r}`);
 rowRange.format.rowHeight=campus?Math.max(22,lines*12+4):Math.max(38,lines*14+10);
 if(campus) {
  rowRange.format.fill=i%2===0?'#FFFFFF':palette.stripe;
  rowRange.format.borders={bottom:{style:'thin',color:palette.rule}};
  sheet.getRange(`F${r}:G${r}`).format.fill='#FFFCF8';
  sheet.getRange(`H${r}`).format.fill=i%2===0?'#FFFDFB':'#FAF6F2';
 }
}
sheet.freezePanes.freezeRows(4);
wb.recalculate();
if (input.render) {
  const image=await wb.render({sheetName:'投递台账',range:`A1:H${Math.min(end,17)}`,scale:1.2,format:'png'});
  await fs.writeFile(path.join(path.dirname(args.output),'台账预览.png'),new Uint8Array(await image.arrayBuffer()));
  const check=await wb.inspect({kind:'region',sheetId:'投递台账',range:`A4:H${Math.min(end,8)}`,maxChars:2000});
  await fs.writeFile(path.join(path.dirname(args.output),'.inspection.json'),check.ndjson,'utf8');
}
const output=await SpreadsheetFile.exportXlsx(wb);
await output.save(args.output);
console.log(JSON.stringify({rows:input.rows.length,output:args.output}));
