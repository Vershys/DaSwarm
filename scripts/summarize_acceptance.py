"""Only a full PostgreSQL + Docker + browser evidence set can pass the P0 gate."""
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
root=Path('test-evidence');matrix={f'A{i:02}':{'status':'BLOCKED','evidence':[]} for i in range(1,29)}
def junit(path,label):
    found={}
    if not path.exists():return found
    for t in ET.parse(path).iter('testcase'):
        status='FAIL' if t.find('failure') is not None or t.find('error') is not None else 'BLOCKED' if t.find('skipped') is not None else 'PASS'
        for id in re.findall(r'A\d{2}',t.attrib.get('name','')):found[id]={'status':status,'evidence':[label+': '+t.attrib['name']]}
    return found
pg=junit(root/'swarm-postgres.xml','PostgreSQL component test')
browser=junit(root/'swarm-browser.xml','Real-browser acceptance')
full=json.loads((root/'fullstack-acceptance.json').read_text()) if (root/'fullstack-acceptance.json').exists() else {}
for id in matrix:
    required=[pg.get(id)]
    if id in ('A01','A05','A09','A16','A18','A19','A20','A21','A25'):required=[full.get(id)]
    if id=='A02':required=[pg.get(id),full.get(id)]
    if id in ('A06','A07','A23'):required=[browser.get(id)]
    if id=='A10':required=[full.get(id),browser.get(id)]
    if all(x and x['status']=='PASS' for x in required):matrix[id]['status']='PASS'
    elif any(x and x['status']=='FAIL' for x in required):matrix[id]['status']='FAIL'
    matrix[id]['evidence']=[x.get('detail',x.get('evidence')) for x in required if x]
root.mkdir(exist_ok=True);(root/'P0_MATRIX.json').write_text(json.dumps(matrix,indent=2))
for id,result in matrix.items():print(id,result['status'])
sys.exit(0 if all(x['status']=='PASS' for x in matrix.values()) else 1)
