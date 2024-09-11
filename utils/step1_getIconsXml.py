path = 'utils\input'
changelogPath = 'utils\output\changelog.txt'
appfilterPath = 'utils\output\\appfilter.xml'
drawablePath = 'utils\output\drawable.xml'

AppNameList = []
AppNamePinyinList = []

import os
# 获取文件列表
def get_file_list(path):
    # 获取文件列表
    file_list = os.listdir(path)
    # 过滤文件，只保留png，返回的值中截取.png前的部分
    file_list = [file.split('.png')[0] for file in file_list if file.endswith('.png')]
    # 返回文件列表
    return file_list

# 删除文件
def clear_file():
    global appfilterPath,drawablePath,changelogPath
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
    if len(files) == 0:
        print('err：未在utils/input文件夹下找到图标文件！')
        return
    for file in files:
        app_infoes = get_app_info(file)
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
    for i in range(len(AppNameList)):
        if(i>0 and AppNameList[i] != AppNameList[i-1] or len(AppNameList)==1):
            with open(changelogPath, 'a', encoding='utf-8') as f:
                f.write('适配和更新：'+'、'.join(AppNameList))
            with open(drawablePath, 'a', encoding='utf-8') as f:
                f.write('''<item drawable="'''+AppNamePinyinList[i]+'''" />\n''')

    print('appfilter.xml、drawable.xml、changelog.txt文件已生成')
index()