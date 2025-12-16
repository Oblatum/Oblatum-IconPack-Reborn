"""从 appfilter.xml 自动生成/补全 appname.xml。

功能：
- 读取 app/src/main/res/xml/appfilter.xml 中未被 XML 注释掉的 <item ... drawable="..." />
- 提取 component="ComponentInfo{package/activity}" 中的 packageName
- 调用 AppTracker API 查询应用名称
- 将查询到的名称写入 app/src/main/res/xml/appname.xml：<item drawable="xxx" cn="名称" />

默认行为：只补全 appname.xml 中缺失的 drawable，不覆盖已有映射。

用法：
  python utils/auto_appname.py
  python utils/auto_appname.py --update
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import ssl
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote
from xml.sax.saxutils import escape


DEFAULT_APPFILTER = Path("app/src/main/res/xml/appfilter.xml")
DEFAULT_APPNAME = Path("app/src/main/res/xml/appname.xml")


APPNAME_HEADER_COMMENT = """    <!--
	  用于中文环境下的图标中文名映射（优先显示）。

	  key: 图标文件名（drawable 资源名，不带扩展名），例如 amber_circle
	  value: 中文名，例如 琥珀圆形

	  示例：
	  <item drawable=\"amber_circle\" cn=\"琥珀圆形\" />
	-->"""


def _strip_xml_comments(text: str) -> str:
	# 移除 <!-- ... --> 注释块，避免把注释里的 item 也当成有效条目
	return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def parse_appfilter_items(appfilter_text: str) -> List[Tuple[str, str]]:
	"""返回 (packageName, drawable) 列表（仅 item 标签，且已剔除 XML 注释）。"""

	text = _strip_xml_comments(appfilter_text)

	# 匹配 <item ... component="ComponentInfo{pkg/activity}" ... drawable="xxx" ... />
	# 注意：属性顺序不固定，故使用两个独立捕获。
	item_pattern = re.compile(r"<item\b[^>]*?/?>", flags=re.I)
	component_pattern = re.compile(r'component\s*=\s*"ComponentInfo\{([^}]+)\}"')
	drawable_pattern = re.compile(r'drawable\s*=\s*"([^"]+)"')

	results: List[Tuple[str, str]] = []
	for raw_item in item_pattern.findall(text):
		component_match = component_pattern.search(raw_item)
		drawable_match = drawable_pattern.search(raw_item)
		if not component_match or not drawable_match:
			continue

		component = component_match.group(1)
		drawable = drawable_match.group(1).strip()
		if not drawable:
			continue

		# component: "pkg/activity"（activity 可能以 . 开头）
		if "/" not in component:
			continue
		package_name = component.split("/", 1)[0].strip()
		if not package_name:
			continue

		results.append((package_name, drawable))

	return results


def parse_existing_appname(appname_text: str) -> Dict[str, str]:
	"""解析 appname.xml 现有映射：drawable -> cn"""

	text = _strip_xml_comments(appname_text)
	pattern = re.compile(r'<item\b[^>]*drawable\s*=\s*"([^"]+)"[^>]*cn\s*=\s*"([^"]*)"[^>]*/>', flags=re.I)
	mapping: Dict[str, str] = {}
	for drawable, cn in pattern.findall(text):
		drawable = drawable.strip()
		if not drawable:
			continue
		mapping[drawable] = cn
	return mapping


class ApiSslError(RuntimeError):
	pass


class ApiNotFoundError(RuntimeError):
	pass


def _http_get_json(url: str, *, timeout_s: float = 15.0, verify_ssl: bool = True) -> dict:
	"""优先 requests，其次 urllib。

	注意：某些 Windows 环境（代理/抓包）可能导致证书校验失败，可用 --insecure 关闭校验。
	"""

	try:
		import requests  # type: ignore

		try:
			resp = requests.get(url, timeout=timeout_s, verify=verify_ssl)
			if resp.status_code == 404:
				raise ApiNotFoundError(f"404 Not Found: {url}")
			resp.raise_for_status()
			return resp.json()
		except Exception as e:
			# requests 未安装时不会走到这里；这里主要兜住 SSL 错误
			if "SSLError" in type(e).__name__ or "CERTIFICATE_VERIFY_FAILED" in str(e):
				raise ApiSslError(str(e)) from e
			raise
	except ModuleNotFoundError:
		from urllib.error import URLError
		from urllib.request import Request, urlopen

		ctx = ssl.create_default_context()
		if not verify_ssl:
			ctx = ssl._create_unverified_context()  # nosec - 用户显式选择 --insecure

		req = Request(url, headers={"User-Agent": "auto_appname.py"})
		try:
			with urlopen(req, timeout=timeout_s, context=ctx) as fp:  # nosec - 本地脚本读取公开 API
				return json.loads(fp.read().decode("utf-8"))
		except URLError as e:
			if "CERTIFICATE_VERIFY_FAILED" in str(e) or isinstance(getattr(e, "reason", None), ssl.SSLCertVerificationError):
				raise ApiSslError(str(e)) from e
			if "HTTP Error 404" in str(e):
				raise ApiNotFoundError(f"404 Not Found: {url}") from e
			raise


def query_apptracker_name(
	package_name: str,
	*,
	api_template: str,
	verify_ssl: bool = True,
	timeout_s: float = 15.0,
	encode_regex: bool = True,
) -> Optional[str]:
	# 兼容两类 API：
	# - 旧版：regex={regex}
	# - 新版：byPackageName={package}（swagger: /app-info/search）
	regex_raw = f"^{package_name}$"
	regex_value = quote(regex_raw, safe="") if encode_regex else regex_raw
	package_value = quote(package_name, safe="")
	url = api_template.format(regex=regex_value, package=package_value)
	data = _http_get_json(url, timeout_s=timeout_s, verify_ssl=verify_ssl)

	def pick_name(app: dict) -> Optional[str]:
		# 新版 swagger: AppInfoDTO.defaultName + localizedName[]
		localized = app.get("localizedName")
		if localized is None:
			# swagger 实际返回字段为 localizedNames
			localized = app.get("localizedNames")
		if isinstance(localized, list):
			preferred_langs = (
				"zh-Hans",
				"zh-Hans-CN",
				"zh-CN",
				"zh",
				"zh-Hant",
				"zh-TW",
			)
			by_lang: Dict[str, str] = {}
			for entry in localized:
				if not isinstance(entry, dict):
					continue
				lang = entry.get("languageCode")
				nm = entry.get("name")
				if isinstance(lang, str) and isinstance(nm, str) and nm.strip():
					by_lang[lang] = nm.strip()
			for lang in preferred_langs:
				if lang in by_lang:
					return by_lang[lang]

		for key in ("defaultName", "appName", "name"):
			value = app.get(key)
			if isinstance(value, str) and value.strip():
				return value.strip()
		return None

	def to_items(payload) -> List[dict]:
		if isinstance(payload, dict):
			items = payload.get("items")
			if isinstance(items, list):
				return [x for x in items if isinstance(x, dict)]
			data = payload.get("data")
			if isinstance(data, list):
				return [x for x in data if isinstance(x, dict)]
			results = payload.get("results")
			if isinstance(results, list):
				return [x for x in results if isinstance(x, dict)]
			return []
		if isinstance(payload, list):
			return [x for x in payload if isinstance(x, dict)]
		return []

	items = to_items(data)
	if not items:
		return None

	# 优先取 packageName 完全匹配的项
	exact = None
	for app in items:
		pkg = app.get("packageName")
		if isinstance(pkg, str) and pkg == package_name:
			exact = app
			break

	chosen = exact or items[0]
	return pick_name(chosen)


def build_drawable_to_package(pairs: Iterable[Tuple[str, str]]) -> Dict[str, str]:
	"""为每个 drawable 选择一个 package（同 drawable 多条时取第一条）。"""
	result: Dict[str, str] = {}
	for package_name, drawable in pairs:
		if drawable not in result:
			result[drawable] = package_name
	return result


def render_appname_xml(mapping: Dict[str, str]) -> str:
	lines: List[str] = [
		'<?xml version="1.0" encoding="utf-8"?>',
		"<appnames>",
		APPNAME_HEADER_COMMENT,
	]

	for drawable in sorted(mapping.keys()):
		cn = mapping[drawable]
		lines.append(f'    <item drawable="{escape(drawable)}" cn="{escape(cn)}" />')
	lines.append("</appnames>")
	lines.append("")
	return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
	parser = argparse.ArgumentParser(description="从 appfilter.xml 查询 API 并补全 appname.xml")
	parser.add_argument("--appfilter", default=str(DEFAULT_APPFILTER), help="appfilter.xml 路径")
	parser.add_argument("--appname", default=str(DEFAULT_APPNAME), help="appname.xml 路径")
	parser.add_argument("--update", action="store_true", help="覆盖 appname.xml 中已存在的 drawable 映射")
	parser.add_argument("--dry-run", action="store_true", help="只打印统计，不写文件")
	parser.add_argument("--insecure", action="store_true", help="关闭 HTTPS 证书校验（仅在证书报错时使用）")
	parser.add_argument("--max", type=int, default=0, help="最多处理多少个 drawable（0 表示不限制）")
	parser.add_argument("--timeout", type=float, default=15.0, help="API 请求超时（秒）")
	parser.add_argument(
		"--api-template",
		default="https://apptracker.sg.butanediol.me/app-info/search?byPackageName={package}",
		help="API URL 模板：支持 {package} 或 {regex} 占位符",
	)
	parser.add_argument("--no-regex-encode", action="store_true", help="不对 regex 参数做 URL 编码")
	args = parser.parse_args(argv)

	appfilter_path = Path(args.appfilter)
	appname_path = Path(args.appname)

	if not appfilter_path.exists():
		print(f"err: 找不到 appfilter.xml：{appfilter_path}")
		return 2
	if not appname_path.exists():
		print(f"err: 找不到 appname.xml：{appname_path}")
		return 2

	appfilter_text = appfilter_path.read_text(encoding="utf-8")
	appname_text = appname_path.read_text(encoding="utf-8")

	pairs = parse_appfilter_items(appfilter_text)
	drawable_to_package = build_drawable_to_package(pairs)
	existing = parse_existing_appname(appname_text)

	total_drawables = len(drawable_to_package)
	print(f"appfilter drawable 总数：{total_drawables}")
	print(f"appname 已有映射数：{len(existing)}")
	if args.insecure:
		print("warn: 已启用 --insecure，HTTPS 证书校验已关闭")
		# 避免 urllib3 InsecureRequestWarning 刷屏
		try:
			import warnings

			from urllib3.exceptions import InsecureRequestWarning  # type: ignore

			warnings.simplefilter("ignore", InsecureRequestWarning)
		except Exception:
			pass

	package_cache: Dict[str, Optional[str]] = {}
	added = 0
	updated = 0
	api_miss = 0

	merged = dict(existing)
	processed = 0
	for drawable, package_name in drawable_to_package.items():
		if not args.update and drawable in existing:
			continue

		if args.max and processed >= args.max:
			break

		processed += 1

		if package_name not in package_cache:
			try:
				package_cache[package_name] = query_apptracker_name(
					package_name,
					api_template=args.api_template,
					verify_ssl=not args.insecure,
					timeout_s=args.timeout,
					encode_regex=not args.no_regex_encode,
				)
			except ApiSslError as e:
				print("err: HTTPS 证书校验失败，无法访问 API。")
				print(f"detail: {e}")
				print("解决方案：")
				print("  1) 先安装 requests 试试（可避免部分 urllib/证书问题）")
				print("  2) 或在确认网络环境安全的前提下使用 --insecure")
				return 3
			except ApiNotFoundError as e:
				print("err: API 返回 404 Not Found（接口路径可能已变更/不可用）。")
				print(f"detail: {e}")
				print("解决方案：")
				print("  1) 用 --api-template 指向新的接口地址")
				print("  2) 或确认域名/路径是否可访问")
				return 4
			except Exception as e:
				print(f"warn: API 查询失败 {package_name}: {e}")
				package_cache[package_name] = None

		app_cn = package_cache[package_name]
		if not app_cn:
			api_miss += 1
			continue

		if drawable in merged:
			if merged[drawable] != app_cn:
				merged[drawable] = app_cn
				updated += 1
		else:
			merged[drawable] = app_cn
			added += 1

	print(f"API 命中写入：新增 {added}，更新 {updated}，未命中 {api_miss}")

	if args.dry_run:
		print("dry-run: 未写入文件")
		return 0

	out = render_appname_xml(merged)
	appname_path.write_text(out, encoding="utf-8")
	print(f"ok: 已写入 {appname_path}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

