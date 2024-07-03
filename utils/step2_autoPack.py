import os
import re


single_mark = '<!-- oblatum autoPack location -->'
double_mark_start = '<!-- oblatum autoPack location start -->'
double_mark_end = '<!-- oblatum autoPack location end -->'

appfilter_path = os.path.join(os.getcwd(), os.path.dirname('app/src/main/res/xml/'), 'appfilter.xml')
drawable_path = os.path.join(os.getcwd(), os.path.dirname('app/src/main/res/xml/'), 'drawable.xml')
changelog_path = os.path.join(os.getcwd(), os.path.dirname('app/src/main/res/xml/'), 'changelog.xml')
myapp_file_path = os.path.join(os.getcwd(), 'buildSrc\src\main\java\MyApp.kt')

if not os.path.exists(appfilter_path):
    print("没有找到 appfilter.xml，请确认当前工作目录为图标包根目录，其中应该包含 gradle, app 文件夹。")
    exit()

def get_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()
    
def get_iconPackInfo():
    myapp_file = get_file(myapp_file_path)
    # 获取图标包信息
    iconPackInfo = {}
    iconPackInfo['versionName'] = myapp_file.split('versionName = "')[1].split('"')[0]
    iconPackInfo['versionCode'] = myapp_file.split('version = ')[1].split('\n')[0]
    return iconPackInfo

def set_iconPackInfo():
    iconPackInfo = get_iconPackInfo()
    # 请输入新版本号（当前版本号为 1.0.0，回车默认不更替）：
    new_versionName = input('请输入新版本（当前版本为 '+iconPackInfo['versionName']+'，回车默认不更替）：')
    if new_versionName != '':
        new_versionCode = str(int(iconPackInfo['versionCode'])+1)
        # 更新 Myapp.kt 文件中的版本号
        myapp_file = get_file(myapp_file_path)
        myapp_file = myapp_file.replace('versionName = "'+iconPackInfo['versionName']+'"', 'versionName = "'+new_versionName+'"')
        myapp_file = myapp_file.replace('version = '+iconPackInfo['versionCode'], 'version = '+str(new_versionCode))
        with open(myapp_file_path, "w" ,encoding='utf-8') as f:
            f.write(myapp_file)
            print(f"\033[92m MyApp.kt 中的版本号已更新到{new_versionName}({new_versionCode}) \033[0m")
    else:
        print(f"MyApp.kt 中的版本号：{iconPackInfo['versionName']}({iconPackInfo['versionCode']})")


def autoPackAppfilter():
    appfilter = get_file(appfilter_path)
    # 在 appfilter.xml 中查找single_mark的位置
    if single_mark not in appfilter:
        print("appfilter.xml 中没有找到标记，请确认是否已经添加标记。")
        exit()
    # 读取output下的appfilter.xml文件
    output_appfilter_path = os.path.join(os.getcwd(), 'utils\output', 'appfilter.xml')
    output_appfilter = get_file(output_appfilter_path)
    output_appfilter = output_appfilter.replace('<','\t\t<')
    version_tag = '<!-- AutoPack: add in v'+get_iconPackInfo()['versionName']+' -->'
    appfilter = appfilter.replace(single_mark, version_tag+'\n' + output_appfilter + '\n\t\t' + single_mark)
    with open(appfilter_path, "w" ,encoding='utf-8') as f:
        f.write(appfilter)
        print("\033[92mappfilter.xml 已更新。\033[0m")

def autoPackDrawable():
    all_tag = '''<category title="All" /><!-- All icons here -->\n'''
    drawable = get_file(drawable_path)
    # 在 drawable.xml 中查找double_mark_start和double_mark_end的位置，在其间添加<test />
    if double_mark_start not in drawable or double_mark_end not in drawable:
        print("drawable.xml 中没有找到标记，请确认是否已经添加标记。")
        exit()
    # 读取output下的drawable.xml文件
    output_drawable_path = os.path.join(os.getcwd(), 'utils\output', 'drawable.xml')
    output_drawable = get_file(output_drawable_path)
    output_drawable = output_drawable.replace('<','\t\t<')
    # 先删除原有的内容
    drawable = drawable.replace(drawable.split(double_mark_start)[1].split(double_mark_end)[0], '\n\t\t')
    # 添加新内容
    drawable = drawable.replace(double_mark_start, double_mark_start + '\n' + output_drawable)

    all = drawable.split(all_tag)[1].split('\n\n')[0]
    all = all+'\n'+output_drawable
    array = all.split('\n')
    array = list(dict.fromkeys(array))
    array.sort()
    new_all = '\n'.join(array)
    drawable = drawable.replace(drawable.split(all_tag)[1].split('\n\n')[0], new_all)

    # 保存到output
    with open(drawable_path, "w" ,encoding='utf-8') as f:
        f.write(drawable)
        print("\033[92mdrawable.xml 已更新。\033[0m")

def autoPackChangelog():
    changelog = get_file(changelog_path)
    # 在 changelog.xml 中查找double_mark_start和double_mark_end的位置，在其间添加<test />
    if double_mark_start not in changelog or double_mark_end not in changelog:
        print("changelog.xml 中没有找到标记，请确认是否已经添加标记。")
        exit()
    # 读取output下的changelog.xml文件
    output_changelog_path = os.path.join(os.getcwd(), 'utils\output', 'changelog.txt')
    output_changelog = get_file(output_changelog_path)
    output_changelog = output_changelog.split('\n')

    # 先删除原有的内容
    changelog = changelog.replace(changelog.split(double_mark_start)[1].split(double_mark_end)[0], '\n\t\t')
    changelog_template='''\t\t<item text="{item}" />\n'''
    # 添加新内容
    changelog_items=[double_mark_start]
    for item in output_changelog:
        changelog_items.append(changelog_template.format(item=item))
    changelog = changelog.replace(double_mark_start, '\n'.join(changelog_items) )
    changelog = changelog.replace(changelog.split('''<version title="''')[1].split('" />')[0], "v"+get_iconPackInfo()['versionName'])
    with open(changelog_path, "w" ,encoding='utf-8') as f:
        f.write(changelog)
        print("\033[92mchangelog.xml 已更新。\033[0m")

from shutil import copyfile
import tkinter
def check_image_size(icon_path):
    root = tkinter.Tk()
    root.withdraw()  # 隐藏窗口
    img = tkinter.PhotoImage(file=icon_path)
    if img.width() != 192 or img.height() != 192:
        print(f"\033[91m{icon_path} 图标尺寸不是192*192，请检查。\033[0m")
        exit()
    root.destroy()  # 销毁窗口

def autoPackIcons():
    icons_path = os.path.join(os.getcwd(), 'utils\output\icons')
    icons = os.listdir(icons_path)
    # 检查图标是否是192*192
    for icon in icons:
        icon_path = os.path.join(icons_path, icon)
        check_image_size(icon_path)
    # 将icons复制到app\src\main\res\drawable-nodpi
    drawable_nodpi_path = os.path.join(os.getcwd(), 'app\src\main\\res\drawable-nodpi')
    for icon in icons:
        icon_path = os.path.join(icons_path, icon)
        copyfile(icon_path, os.path.join(drawable_nodpi_path, icon))
    print("\033[92m图标已复制到 app\src\main\res\drawable-nodpi。\033[0m")


# set_iconPackInfo()
# autoPackAppfilter()
# autoPackDrawable()
# autoPackChangelog()
autoPackIcons()
