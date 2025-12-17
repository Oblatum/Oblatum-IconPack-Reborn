"""从 appfilter.xml 自动生成/补全 appname.xml。

功能：
- 读取 app/src/main/res/xml/appfilter.xml 中未被 XML 注释掉的 <item ... drawable="..." />
- 提取 component="ComponentInfo{package/activity}" 中的 packageName
- 调用 AppTracker API 查询应用名称
- 将查询到的名称写入 appname.xml：<item drawable="xxx" name="..." />

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
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote
from xml.sax.saxutils import escape


DEFAULT_APPFILTER = Path("app/src/main/res/xml/appfilter.xml")
DEFAULT_APPNAME_EN = Path("app/src/main/res/xml/appname.xml")
DEFAULT_APPNAME_ZH = Path("app/src/main/res/xml-zh/appname.xml")
DEFAULT_APPNAME_ZH_RCN = Path("app/src/main/res/xml-zh-rCN/appname.xml")


APPNAME_HEADER_COMMENT_EN = """    <!--
			Default (fallback) icon name mapping.
			key: drawable resource name (without extension)
			value: display name

			Example:
			<item drawable=\"amber_circle\" name=\"Amber Circle\" />
		-->"""

APPNAME_HEADER_COMMENT_ZH = """    <!--
			zh（中文）环境下的图标名称映射（当该图标没有对应已安装应用时使用）。

			key: 图标文件名（drawable 资源名，不带扩展名），例如 amber_circle
			value: 显示名称，例如 琥珀圆形

			示例：
			<item drawable=\"amber_circle\" name=\"琥珀圆形\" />
		-->"""

APPNAME_HEADER_COMMENT_ZH_RCN = """    <!--
			zh-rCN（简体中文/中国）环境下的图标名称映射。

			key: 图标文件名（drawable 资源名，不带扩展名），例如 amber_circle
			value: 显示名称，例如 琥珀圆形

			示例：
			<item drawable=\"amber_circle\" name=\"琥珀圆形\" />
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
	"""解析 appname.xml 现有映射：drawable -> name。

	兼容旧格式（cn="..."），但旧格式会被视为“无有效映射”，避免迁移期跳过写入。
	"""

	text = _strip_xml_comments(appname_text)

	# 新格式：name="..."
	pattern_name = re.compile(r'<item\b[^>]*drawable\s*=\s*"([^"]+)"[^>]*name\s*=\s*"([^"]*)"[^>]*/>', flags=re.I)
	mapping: Dict[str, str] = {}
	for drawable, name in pattern_name.findall(text):
		drawable = drawable.strip()
		if not drawable:
			continue
		mapping[drawable] = name

	# 旧格式存在但新格式没有：返回空，强制本次生成覆盖写入
	if mapping:
		return mapping

	pattern_cn = re.compile(r'<item\b[^>]*drawable\s*=\s*"([^"]+)"[^>]*cn\s*=\s*"([^"]*)"[^>]*/>', flags=re.I)
	if pattern_cn.search(text):
		return {}

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
		from requests import exceptions as req_exc  # type: ignore

		def _is_cert_verify_error(err: BaseException) -> bool:
			text = str(err)
			return (
				"CERTIFICATE_VERIFY_FAILED" in text
				or "certificate verify failed" in text
				or isinstance(err, ssl.SSLCertVerificationError)
			)

		# 轻量重试：处理网络抖动/EOF/超时（不包含证书校验失败）
		last_error: Optional[BaseException] = None
		for attempt in range(3):
			try:
				# timeout 支持 (connect, read)，避免连接成功但读取卡住
				resp = requests.get(url, timeout=(timeout_s, timeout_s), verify=verify_ssl)
				if resp.status_code == 404:
					raise ApiNotFoundError(f"404 Not Found: {url}")
				resp.raise_for_status()
				return resp.json()
			except ApiNotFoundError:
				raise
			except req_exc.SSLError as e:
				# 证书校验失败：直接报错退出；其他 SSL 错误（比如 EOF）按网络错误重试/降级
				if _is_cert_verify_error(e):
					raise ApiSslError(str(e)) from e
				last_error = e
			except (req_exc.Timeout, req_exc.ConnectionError) as e:
				last_error = e
			except Exception as e:
				# 其他错误不重试
				raise

			# 非最后一次则退避
			if attempt < 2:
				time.sleep(1.0 * (attempt + 1))

		raise last_error if last_error else RuntimeError("Unknown HTTP error")
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


def query_apptracker_name(*args, **kwargs):  # pragma: no cover
	"""兼容旧接口：已弃用。

	之前版本返回单一名称；现在需要分别生成 zh/zh-rCN/en 三份映射。
	"""
	raise RuntimeError("query_apptracker_name 已弃用，请使用 query_apptracker_app + pick_localized_name")


def build_drawable_to_package(pairs: Iterable[Tuple[str, str]]) -> Dict[str, str]:
	"""为每个 drawable 选择一个 package（同 drawable 多条时取第一条）。"""
	result: Dict[str, str] = {}
	for package_name, drawable in pairs:
		if drawable not in result:
			result[drawable] = package_name
	return result


_CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")


def _contains_chinese(text: str) -> bool:
	return bool(_CHINESE_CHAR_RE.search(text))


def render_appname_xml(mapping: Dict[str, str], *, header_comment: str) -> str:
	lines: List[str] = [
		'<?xml version="1.0" encoding="utf-8"?>',
		"<appnames>",
		header_comment,
	]

	for drawable in sorted(mapping.keys()):
		name = mapping[drawable]
		lines.append(f'    <item drawable="{escape(drawable)}" name="{escape(name)}" />')
	lines.append("</appnames>")
	lines.append("")
	return "\n".join(lines)


def query_apptracker_app(
	package_name: str,
	*,
	api_template: str,
	verify_ssl: bool = True,
	timeout_s: float = 15.0,
	encode_regex: bool = True,
) -> Optional[dict]:
	"""返回单个 app 的 JSON dict（优先 packageName 精确匹配）。"""

	regex_raw = f"^{package_name}$"
	regex_value = quote(regex_raw, safe="") if encode_regex else regex_raw
	package_value = quote(package_name, safe="")
	url = api_template.format(regex=regex_value, package=package_value)
	data = _http_get_json(url, timeout_s=timeout_s, verify_ssl=verify_ssl)

	def to_items(payload) -> List[dict]:
		if isinstance(payload, dict):
			items = payload.get("items")
			if isinstance(items, list):
				return [x for x in items if isinstance(x, dict)]
			data2 = payload.get("data")
			if isinstance(data2, list):
				return [x for x in data2 if isinstance(x, dict)]
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

	for app in items:
		pkg = app.get("packageName")
		if isinstance(pkg, str) and pkg == package_name:
			return app

	return items[0]


def pick_localized_name(app: dict, preferred_language_codes: Tuple[str, ...]) -> Optional[str]:
	localized = app.get("localizedNames")
	if localized is None:
		localized = app.get("localizedName")

	if isinstance(localized, list):
		by_lang: Dict[str, str] = {}
		for entry in localized:
			if not isinstance(entry, dict):
				continue
			lang = entry.get("languageCode")
			nm = entry.get("name")
			if isinstance(lang, str) and isinstance(nm, str) and nm.strip():
				by_lang[lang] = nm.strip()
		for lang in preferred_language_codes:
			if lang in by_lang:
				return by_lang[lang]
	return None


def main(argv: Optional[List[str]] = None) -> int:
	parser = argparse.ArgumentParser(description="从 appfilter.xml 查询 API 并补全 appname.xml")
	parser.add_argument("--appfilter", default=str(DEFAULT_APPFILTER), help="appfilter.xml 路径")
	parser.add_argument("--appname-en", default=str(DEFAULT_APPNAME_EN), help="默认(英文/回退) appname.xml 路径")
	parser.add_argument("--appname-zh", default=str(DEFAULT_APPNAME_ZH), help="xml-zh/appname.xml 路径")
	parser.add_argument("--appname-zh-rCN", default=str(DEFAULT_APPNAME_ZH_RCN), help="xml-zh-rCN/appname.xml 路径")
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
	appname_en_path = Path(args.appname_en)
	appname_zh_path = Path(args.appname_zh)
	appname_zh_rcn_path = Path(getattr(args, "appname_zh_rCN"))

	if not appfilter_path.exists():
		print(f"err: 找不到 appfilter.xml：{appfilter_path}")
		return 2
	for p in (appname_en_path, appname_zh_path, appname_zh_rcn_path):
		if not p.exists():
			print(f"err: 找不到 appname.xml：{p}")
			return 2

	appfilter_text = appfilter_path.read_text(encoding="utf-8")
	appname_en_text = appname_en_path.read_text(encoding="utf-8")
	appname_zh_text = appname_zh_path.read_text(encoding="utf-8")
	appname_zh_rcn_text = appname_zh_rcn_path.read_text(encoding="utf-8")

	pairs = parse_appfilter_items(appfilter_text)
	drawable_to_package = build_drawable_to_package(pairs)
	existing_en = parse_existing_appname(appname_en_text)
	existing_zh = parse_existing_appname(appname_zh_text)
	existing_zh_rcn = parse_existing_appname(appname_zh_rcn_text)

	total_drawables = len(drawable_to_package)
	print(f"appfilter drawable 总数：{total_drawables}")
	print(f"appname 已有映射数：en {len(existing_en)} / zh {len(existing_zh)} / zh-rCN {len(existing_zh_rcn)}")
	if args.insecure:
		print("warn: 已启用 --insecure，HTTPS 证书校验已关闭")
		# 避免 urllib3 InsecureRequestWarning 刷屏
		try:
			import warnings

			from urllib3.exceptions import InsecureRequestWarning  # type: ignore

			warnings.simplefilter("ignore", InsecureRequestWarning)
		except Exception:
			pass

	package_cache: Dict[str, Optional[dict]] = {}

	added_en = updated_en = miss_en = skipped_en = 0
	added_zh = updated_zh = miss_zh = 0
	added_zh_rcn = updated_zh_rcn = miss_zh_rcn = 0

	merged_en = dict(existing_en)
	merged_zh = dict(existing_zh)
	merged_zh_rcn = dict(existing_zh_rcn)
	processed = 0
	interrupted = False
	try:
		for drawable, package_name in drawable_to_package.items():
			# 仅当三份文件都已有该 drawable，才跳过；否则补齐缺失的语言版本
			if not args.update and (drawable in existing_en and drawable in existing_zh and drawable in existing_zh_rcn):
				continue

			if args.max and processed >= args.max:
				break

			processed += 1

			if package_name not in package_cache:
				try:
					package_cache[package_name] = query_apptracker_app(
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

			app = package_cache[package_name]
			if not app:
				miss_en += 1
				miss_zh += 1
				miss_zh_rcn += 1
				continue

			# zh / zh-rCN：按你的规则优先级：zh-CN > zh-rCN > zh-Hans-CN
			zh_name = pick_localized_name(app, ("zh-CN", "zh-rCN", "zh-Hans-CN"))
			if zh_name:
				if drawable in merged_zh:
					if args.update and merged_zh[drawable] != zh_name:
						merged_zh[drawable] = zh_name
						updated_zh += 1
				else:
					merged_zh[drawable] = zh_name
					added_zh += 1
			else:
				miss_zh += 1

			zh_rcn_name = pick_localized_name(app, ("zh-CN", "zh-rCN", "zh-Hans-CN"))
			if zh_rcn_name:
				if drawable in merged_zh_rcn:
					if args.update and merged_zh_rcn[drawable] != zh_rcn_name:
						merged_zh_rcn[drawable] = zh_rcn_name
						updated_zh_rcn += 1
				else:
					merged_zh_rcn[drawable] = zh_rcn_name
					added_zh_rcn += 1
			else:
				miss_zh_rcn += 1

			# en：只使用 en-US；若 en-US 含中文则整条跳过；禁止 fallback defaultName
			en_name = pick_localized_name(app, ("en-US",))
			force_skip_en = False
			if en_name and _contains_chinese(en_name):
				skipped_en += 1
				force_skip_en = True
				en_name = None

			if en_name:
				if drawable in merged_en:
					if args.update and merged_en[drawable] != en_name:
						merged_en[drawable] = en_name
						updated_en += 1
				else:
					merged_en[drawable] = en_name
					added_en += 1
			else:
				miss_en += 1
	except KeyboardInterrupt:
		interrupted = True
		print("warn: 检测到中断(KeyboardInterrupt)，将写入已获取到的部分结果…")

	print(
		"API 命中写入："
		f"en 新增 {added_en} 更新 {updated_en} 未命中 {miss_en} 跳过(含中文) {skipped_en}；"
		f"zh 新增 {added_zh} 更新 {updated_zh} 未命中 {miss_zh}；"
		f"zh-rCN 新增 {added_zh_rcn} 更新 {updated_zh_rcn} 未命中 {miss_zh_rcn}"
	)

	if args.dry_run:
		print("dry-run: 未写入文件")
		return 0

	out_en = render_appname_xml(merged_en, header_comment=APPNAME_HEADER_COMMENT_EN)
	out_zh = render_appname_xml(merged_zh, header_comment=APPNAME_HEADER_COMMENT_ZH)
	out_zh_rcn = render_appname_xml(merged_zh_rcn, header_comment=APPNAME_HEADER_COMMENT_ZH_RCN)

	for p in (appname_en_path, appname_zh_path, appname_zh_rcn_path):
		p.parent.mkdir(parents=True, exist_ok=True)

	appname_en_path.write_text(out_en, encoding="utf-8")
	appname_zh_path.write_text(out_zh, encoding="utf-8")
	appname_zh_rcn_path.write_text(out_zh_rcn, encoding="utf-8")
	print(f"ok: 已写入 {appname_en_path}")
	print(f"ok: 已写入 {appname_zh_path}")
	print(f"ok: 已写入 {appname_zh_rcn_path}")
	return 130 if interrupted else 0


if __name__ == "__main__":
	raise SystemExit(main())

