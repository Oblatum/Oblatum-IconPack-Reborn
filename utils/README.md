# Oblatum AutoPack
**Version:** 1.0 **Date:** 2024-06-07
## 第一步
1. 将图标文件以**包名**命名放在utils\input文件夹中
2. 运行step1_getIconsXml.py，期间可能需要修改不规范的名称
- 你将得到：output\icons\**.png、appfilter.xml、drawable.xml、changelog.txt
## 第二步
1. 运行step2_autoPack.py，输入版本号即可
2. 检查appfilter.xml、drawable.xml等文件
## 第三步
1. 运行step3_filecopy.py