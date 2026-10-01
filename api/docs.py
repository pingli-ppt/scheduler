"""中文增强版 Swagger 接口文档页面。"""

from __future__ import annotations

from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse


CHINESE_UI_SCRIPT = r"""
<script>
(() => {
  document.documentElement.lang = "zh-CN";
  const translations = new Map([
    ["Authorize", "接口授权"],
    ["Available authorizations", "可用授权方式"],
    ["Close", "关闭"],
    ["Cancel", "取消"],
    ["Clear", "清空"],
    ["Reset", "重置"],
    ["Try it out", "在线测试"],
    ["Execute", "发送请求"],
    ["Download", "下载"],
    ["Parameters", "参数说明"],
    ["No parameters", "无需参数"],
    ["Request body", "请求内容"],
    ["Request URL", "请求地址"],
    ["Server response", "服务器返回"],
    ["Responses", "返回结果"],
    ["Response body", "返回内容"],
    ["Response headers", "返回头信息"],
    ["Code", "状态码"],
    ["Details", "详细信息"],
    ["Description", "说明"],
    ["Name", "名称"],
    ["Required", "必填"],
    ["Default", "默认值"],
    ["Example", "示例"],
    ["Example Value", "示例值"],
    ["Value", "值"],
    ["Schema", "字段结构"],
    ["Schemas", "数据结构"],
    ["Models", "数据结构"],
    ["Model", "数据结构"],
    ["Media type", "数据格式"],
    ["Successful Response", "请求成功"],
    ["Validation Error", "输入数据校验失败"],
    ["Controls Accept header.", "用于设置返回数据格式。"],
    ["Links", "相关链接"],
    ["Scopes", "权限范围"],
    ["Select a definition", "选择数据结构"]
    ,["string", "文本"]
    ,["string($date)", "日期文本"]
    ,["integer", "整数"]
    ,["number", "数字"]
    ,["boolean", "是/否"]
    ,["array", "列表"]
    ,["object", "对象"]
    ,["body", "请求内容"]
    ,["path", "路径参数"]
    ,["query", "查询参数"]
    ,["ChildInput", "儿童档案填写内容"]
    ,["ScheduleInput", "排程填写内容"]
    ,["EngagementInput", "采纳与摄入填写内容"]
    ,["OutcomeInput", "结果上报填写内容"]
    ,["DailyIntakeInput", "每日膳食填写内容"]
    ,["HTTPValidationError", "接口校验错误"]
    ,["ValidationError", "字段校验错误"]
  ]);

  let scheduled = false;
  function translatePage() {
    scheduled = false;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const raw = node.nodeValue;
      const text = raw.trim();
      const translated = translations.get(text);
      if (translated) node.nodeValue = raw.replace(text, translated);
    }
  }

  function scheduleTranslation() {
    if (scheduled) return;
    scheduled = true;
    window.setTimeout(translatePage, 20);
  }

  new MutationObserver(scheduleTranslation).observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true
  });
  window.addEventListener("load", scheduleTranslation);
  scheduleTranslation();
})();
</script>
"""


def chinese_swagger_ui(openapi_url: str, title: str) -> HTMLResponse:
    """返回保留 Swagger 测试能力、并补充常用中文界面词的文档页面。"""

    response = get_swagger_ui_html(
        openapi_url=openapi_url,
        title=title,
        swagger_ui_parameters={
            "defaultModelsExpandDepth": 1,
            "docExpansion": "list",
            "displayRequestDuration": True,
        },
    )
    html = response.body.decode("utf-8").replace(
        "</body>",
        f"{CHINESE_UI_SCRIPT}</body>",
    )
    return HTMLResponse(content=html, status_code=response.status_code)
