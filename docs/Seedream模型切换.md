# Seedream 模型切换 · 2026-11-06

## 当前生效方案：Seedream 5.0 Flash

用户提供控制台调用示例并明确改用 doubao-seedream-5-0-flash-260915。当前默认模型及环境示例已更新为 Flash；分身与试穿仍通过同一个服务端模块调用。移除 Lite 的组图字段，不提交 stream；使用单图同步返回、JPEG Base64 响应、1664x2496 竖版，并保留服务商水印。

真实图生图调用成功：复用此前已生成的测试人物照，不使用用户私照；请求一张全身棚拍图，18.2 秒收到图片，应用转换后的尺寸为 1024x1536。结果仅保存在被 Git 忽略的 .secrets/seedream-flash-verification.jpg。本次没有真实多件服饰试穿质量评测，不能据此保证换装效果。

4 个隔离测试通过，覆盖七张参考图的请求字段及解析、鉴权失败、超时不重试、空返回。Python 语法检查通过。代码修改及真实图生图验证已完成；随后按用户“现在修改上线”的明确授权部署。

官方参数参考：https://docs.volcengine.com/docs/ark/seedream-5-0-pro?lang=zh

以下为此前 Lite 接入失败的历史排查记录，不代表当前 Flash 状态。


用户要求将分身和试穿的生图调用改为火山方舟 Seedream 5.0 Lite。

- 当前服务端入口：local/ark_generation.py，server.py 的全部分身/试穿调用改为此模块，不回退 fal.ai。
- 正式推理 URL：https://ark.cn-beijing.volces.com/api/v3/images/generations。API Explorer 文档页不是推理地址。
- 默认模型：doubao-seedream-5-0-lite-260128；支持服务端 ARK_IMAGE_MODEL 指定用户已开通的同模型推理接入点。
- 密钥：ARK_API_KEY。用户提供的值以当前 Windows 用户 DPAPI 加密保存在 .secrets/ark.key，启动器解密至进程环境。不复制入 Git、前端或本记录。线上环境尚未配置此密钥。
- 人物在参考图第 1 张，衣物按槽位顺序跟随；JPEG data URL 多图输入，单张输出，关闭组图与流式，1664x2496 竖版，返回 b64_json。输出统一缩放到现有应用尺寸。保留服务商水印与 APP 导出标识。
- 明确处理无权限、限流、无图和网络超时；超时不自动重试，避免隐性重复消费。当前原有的任务持久化缺口没有由模型切换自动解决。
- /api/avatar/options 提供 ready、provider、model，不返回密钥。页面照片授权说明同步改为火山方舟 Seedream。

## 验证结果与阻塞

4 个隔离测试通过：多图请求顺序与字段、图片解析、403 信息脱敏且不重试、超时不重试和空结果错误（部分场景合并在同一用例）。Python 语法与外部 JS 语法检查通过。

一次真实图生图调用返回 HTTP 404，错误码 InvalidEndpointOrModel.NotFound，未取得图片。随后仅用缺失 prompt 的参数校验探测（不请求生成），确认官方两个模型标识 doubao-seedream-5-0-lite-260128、doubao-seedream-5-0-260128 均返回无模型/无访问权限。不能据此宣称密钥有效或模型已成功接通，也未切换成其他模型。

需用户在火山方舟北京地域确认已开通 Seedream 5.0 Lite，并为该密钥授予访问；如使用专用推理接入点，可提供 ep- 开头的接入点 ID（非密钥）。配置完成后再做一次真实验证。未部署线上，原线上模型继续运行。

官方依据：https://docs.volcengine.com/docs/ark/image-generation-tutorial?redirect=1&lang=zh

## 补充排查：用户确认普通密钥和模型已开通

同一密钥访问北京地域 GET /api/v3/models 返回 200；无效密钥对照请求返回 401，可确认当前密钥通过该接口鉴权。目录含 doubao-seedream-5-0-260128，支持 images/generations，但状态为 Retiring。这不是账号实际推理授权的证明。两个模型别名的无生成参数探测仍均返回 404 InvalidEndpointOrModel.NotFound。

官方方舟下线公告将该模型列入第十批：2026-09-24 停止新购，2026-11-24 14:00 下线，推荐迁移 5.0 Pro。不能将此公告直接认定为当前 404 的唯一原因；用户现有授权、模型推理接入点与密钥范围仍需核对。下一步优先获取用户控制台 API 调用示例中的 model 值（可能为 ep- 接入点），不需要重新提供密钥，不擅自切换版本。

公告：https://docs.volcengine.com/docs/ark/model-deprecation-notice?lang=zh
本轮仅查询模型目录和缺失 prompt 的参数探测，未生成图片。

## 2026-11-06 线上部署完成

按用户明确授权，https://tryon.example.com 已切换为 doubao-seedream-5-0-flash-260915，分身和试穿共用服务端适配器。服务端密钥通过 SSH 标准输入配置到 root:root 600 的 /etc/tryon/tryon.env，未写入部署包或公开文档。原环境配置保留其他字段。

源代码和环境备份位于 /var/backups/tryon/flash-20261106-165632（备份目录 700）。本次只更新 local/server.py、local/ark_generation.py、web/index.html、web/account-export.js 和生图环境配置，不清理 /var/lib/tryon，不改 Nginx 及其他站点。

验证：服务 active；云端到方舟模型目录鉴权成功；公网 /api/avatar/options 返回 ready=true、provider=volcengine-ark、目标 Flash 模型；首页和外部 JS、/api/me、导出配置返回 200；首页无旧 fal.ai 照片授权文案。私人数据目录仍为 www:www 700，原两个网站 HTTP 入口均为 301。部署检查未额外生成付费图片；此前本机真实图生图测试已成功。短信登录仍取决于其独立配置。
