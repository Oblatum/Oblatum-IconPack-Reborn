path = 'utils\input'
changelogPath = 'utils\output\changelog.txt'
appfilterPath = 'utils\output\\appfilter.xml'
drawablePath = 'utils\output\drawable.xml'

AppNameList = []
AppNamePinyinList = []

import os
import re

def init ():
    # 初始化文件夹
    if not os.path.exists('utils\output'):
        os.makedirs('utils\output')
    if not os.path.exists('utils\output\icons'):
        os.makedirs('utils\output\icons')
# 获取文件列表
def get_file_list(path):
    # 获取文件列表
    file_list = os.listdir(path)
    # 过滤文件，只保留png，返回的值中截取.png前的部分
    file_list = [file.split('.png')[0] for file in file_list if file.endswith('.png')]
    print('共找到'+str(len(file_list))+'个图标文件')
    # 返回文件列表
    return file_list

# 获取appfiler.xml内容
def get_appfilter_content():
    # 检查input中xml文件是否存在，不存在则return[]
    if not os.path.exists('utils/input/appfilter.xml'):
        return []
    with open('utils/input/appfilter.xml', 'r', encoding='utf-8') as f:
        content = f.read()
        # 匹配出packageName、activityName和appName
        # 正则匹配出<item component="ComponentInfo{'''+packageName+'/'+activityName+'''}" drawable="'''+appName+'''"/>
        content = content.split('\n')
        content = [i for i in content if re.match('<item component="ComponentInfo{.*?}" drawable=".*?"/>', i)]
        content = [i.strip() for i in content if i.strip()]
        # 从中解析出packageName、activityName和appName，转为json  <item component="ComponentInfo{io.dcloud.H576E6CC7/io.dcloud.H576E6CC7.launch.LaunchActivity}" drawable="鱼泡直聘"/>
        content = [re.match('<item component="ComponentInfo{(.*?)/(.*?)}" drawable="(.*?)"/>', i).groups() for i in content]
        content = [{'packageName': match[0], 'activityName': match[1], 'appName': match[2]} for match in content]

        # 返回匹配到的内容
        return content

# 删除文件
def clear_file():
    global appfilterPath,drawablePath,changelogPath

    init()
    # 如果文件存在，删除文件
    if os.path.exists(appfilterPath):
        os.remove(appfilterPath)
        print('appfilter.xml文件已存在，删除文件')
    if os.path.exists(drawablePath):
        os.remove(drawablePath)
        print('drawable.xml文件已存在，删除文件')
    if os.path.exists(changelogPath):
        os.remove(changelogPath)
        print('changelog.txt文件已存在，删除文件')
    # 检查icons文件夹是否存在，不存在则创建，存在则删除文件
    if os.path.exists('utils\output\icons'):
        print('icons文件夹已存在，删除文件')
        os.system('rd /s /q output\icons')
    else:os.mkdir('utils\output\icons')

import requests
# 使用api，通过包名查询应用信息
def get_app_info(package_name):
    # 使用包名查询应用信息
    url = "https://apptracker-api.cn2.tiers.top/api/appInfo?per=2147483647&page=1&regex=^"+package_name+"$"
    # 发送请求
    response = requests.get(url)
    # json格式数据
    app_info = response.json().get('items')
    # 返回应用信息
    return app_info

# 解决非常规名称的问题
def appNameCheck(appName):
    # 检查是否包含除0-9、a-z、A-Z、中文、空格、_之外的字符
    for char in appName:
        if not (char.isdigit() or char.isalpha() or char == ' ' or char == '_' or '\u4e00' <= char <= '\u9fa5'):
            print('\033[31m' + '非法AppName：'+appName + '\033[0m')
            print('请输入矫正后的AppName：')
            appName = input()
            return appName,True
    return appName,False

from pypinyin import pinyin, lazy_pinyin, Style
# 根据json数据，生成appfilter.xml
def produce_xml_and_txt(app_info,first_appName,first_appName_pinyin):
    global AppNameList, AppNamePinyinList  # 声明全局变量
    activityName = app_info.get('activityName')
    # 如果first_appName为空，使用appName
    if first_appName == '': 
        appName,check = appNameCheck(app_info.get('appName'))
        # 如果包含非法字符，重新输入
        if check:
            while check:
                appName,check = appNameCheck(appName)
        # appName转为拼音,首字母大写,使用“__”拼接
        appName_pinyin = '__'.join([word.capitalize() for word in lazy_pinyin(appName)]).replace(' ','_').lower()
        # 如果appName_pinyin第一个字符为数字，添加“a_”
        if appName_pinyin[0].isdigit():
            appName_pinyin = 'a_'+appName_pinyin
        with open(appfilterPath, 'a', encoding='utf-8') as f:
            f.write('''<!-- '''+appName+''' -->\n''')
    else:
        appName = first_appName
        appName_pinyin = first_appName_pinyin

    packageName = app_info.get('packageName')
    # 检测appfilter.xml、drawable.xml、和changelog.txt文件是否存在，不存在则创建,存在就追加
    with open(appfilterPath, 'a', encoding='utf-8') as f:
        f.write('''<item component="ComponentInfo{'''+packageName+'/'+activityName+'''}" drawable="'''+appName_pinyin+'''"/>\n''')
    return appName,appName_pinyin
    


def index():
    global AppNameList, AppNamePinyinList  # 声明全局变量
    clear_file()
    files = get_file_list(path)
    err_count = []
    if len(files) == 0:
        print('\033[31m'+'err：未在utils/input文件夹下找到图标文件！'+ '\033[0m')
        return
    for file in files:
        print('-------------------')
        print('正在处理：'+file)
        try:
            app_infoes = get_app_info(file)
        except Exception as e:
            print(f"获取 {file} 的应用信息时出错: {e}")
            app_infoes = []
        if len(app_infoes) == 0:
            
            # 如果未找到应用信息，从appfilter.xml中查找
            appfilter_content = get_appfilter_content()
            for item in appfilter_content:
                if item['packageName'] == file:
                    app_infoes.append(item)
                    break
            if len(app_infoes) == 0:
              err_count.append(file)
              print('\033[31m'+'err：未找到'+file+'的应用信息！'+ '\033[0m')
              continue
        appName,appName_pinyin='',''
        for i in range(len(app_infoes)):
            if(i==0):
                appName,appName_pinyin = produce_xml_and_txt(app_infoes[i],appName,appName_pinyin)
                print(appName)
                AppNameList.append(appName)
                AppNamePinyinList.append(appName_pinyin)
                # 复制file的文件到项目icons文件夹下，并重命名为appName_pinyin
                os.system('copy '+path+'\\'+file+'.png utils\output\\icons\\'+appName_pinyin+'.png')

            else:
                produce_xml_and_txt(app_infoes[i],appName,appName_pinyin)

    # AppNamePinYinList 按字母排序
    AppNamePinyinList = sorted(AppNamePinyinList)
        # ...existing code...
    
    # 去重且保持顺序
    unique_pinyin = []
    seen = set()
    for p in AppNamePinyinList:
        if p not in seen:
            unique_pinyin.append(p)
            seen.add(p)
    for p in unique_pinyin:
        with open(drawablePath, 'a', encoding='utf-8') as f:
            f.write(f'<item drawable="{p}" />\n')
    
    # ...existing code...
    with open(changelogPath, 'a', encoding='utf-8') as f:
        f.write('适配和更新：'+'、'.join(AppNameList))

    print('appfilter.xml、drawable.xml、changelog.txt文件已生成')
    print('共找到'+str(len(files))+'个图标文件，未找到应用信息的有'+len(err_count)+'个')
index()
# print(get_appfilter_content())