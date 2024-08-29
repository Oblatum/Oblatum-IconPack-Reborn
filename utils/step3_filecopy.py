import os

appfilter_path = os.path.join(os.getcwd(), os.path.dirname('app/src/main/res/xml/'), 'appfilter.xml')
drawable_path = os.path.join(os.getcwd(), os.path.dirname('app/src/main/res/xml/'), 'drawable.xml')
if not os.path.exists(appfilter_path):
    print("err：没有找到 appfilter.xml，请确认当前工作目录为图标包根目录，其中应该包含 gradle, app 文件夹。")
    exit()
# 复制 drawable.xml appfilter.xml到 app/src/main/assets/ 目录
from shutil import copyfile
copyfile(drawable_path, os.path.join(os.getcwd(), 'app/src/main/assets/', 'drawable.xml'))
copyfile(appfilter_path, os.path.join(os.getcwd(), 'app/src/main/assets/', 'appfilter.xml'))
print("appfilter.xml、drawable.xml已复制到 app/src/main/assets/ 目录")
