# 读取temp下的appfilter.xml
import os
import sys
import re
appfilter_path = 'utils\\temp\\appfilter.xml'
appfilter={}
finded =[]
unfinded =[]

with open(appfilter_path, 'r', encoding='utf-8') as f:
    # <item component="ComponentInfo{com.android.stk/com.android.stk.OppoStkLauncherActivity1}" drawable="SIM 卡应用程序"/>
    regex = r'<item component="ComponentInfo{(.+?)/(.+?)}" drawable="(.+?)"/>'
    matches = re.finditer(regex, f.read(), re.MULTILINE)

    for matchNum, match in enumerate(matches, start=1):
        package = match.group(1)
        activity = match.group(1)+"/"+match.group(2)
        name = match.group(3)
        appfilter[name] = {'package': package, 'activity': activity, 'name': name}

with open('app/src//main/res/xml/appfilter.xml','r', encoding='utf-8') as f:
    xml = f.read()
    for i in appfilter:
        # 在f中寻找package，如果找到了，就在i中添加true
        if xml.find(appfilter[i]['package']) != -1:
            appfilter[i]['find'] = 'true'
            finded.append(appfilter[i]['name'])
        else:
            appfilter[i]['find'] = 'false'
            unfinded.append(appfilter[i]['name'])

print(appfilter)
print(f'finded: {finded}')
print(f'unfinded: {unfinded}')