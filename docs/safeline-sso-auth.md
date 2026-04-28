# 雷池统一登录与本系统认证接入说明

本文档记录本次关于“是否可以使用雷池做统一登录，并取消本系统本地登录”的沟通结论与当前实现口径。

## 1. 结论

雷池可以作为本系统前置统一登录入口使用。

本系统已保留默认本地账号密码登录，同时新增可配置认证模式，用于接入雷池或其他反向代理统一认证。

推荐方案：

- 只需要雷池统一拦截登录，不要求本系统记录真实用户名：使用 `disabled` 模式。
- 希望审计日志记录统一登录用户名：使用 `proxy` 模式，并让雷池或上游代理向后端传递已认证用户名请求头。

## 2. 认证模式

| 模式 | 适用场景 | 行为 |
|---|---|---|
| `local` | 默认部署、本地开发、未接入统一认证 | 使用系统内置管理员账号密码登录 |
| `disabled` | 雷池已经完成统一登录拦截，但不传递真实用户名 | 关闭本系统登录页，后端使用固定内部审计用户 |
| `proxy` | 雷池或反向代理能传递已认证用户名 | 关闭本系统登录页，后端读取请求头用户名并自动创建内部审计用户 |

## 3. 环境变量配置

### 3.1 保持本地登录

```env
ABS_AUTH_MODE=local
```

这是默认值，不影响原有管理员登录、会话和 CSRF 逻辑。

### 3.2 雷池只做统一登录拦截

```env
ABS_AUTH_MODE=disabled
ABS_AUTH_DISABLED_USERNAME=safeline-admin
```

该模式下：

- 本系统账号密码登录关闭。
- 前端登录页会提示等待统一登录身份。
- 后端所有业务操作使用 `ABS_AUTH_DISABLED_USERNAME` 对应的内部用户写入审计。
- 如果内部用户不存在，系统会自动创建。

### 3.3 雷池传递真实登录用户

```env
ABS_AUTH_MODE=proxy
ABS_AUTH_PROXY_USER_HEADERS=X-Remote-User,X-Forwarded-User,Remote-User,X-Auth-Request-User
```

该模式下：

- 本系统账号密码登录关闭。
- 后端按顺序读取 `ABS_AUTH_PROXY_USER_HEADERS` 中配置的请求头。
- 读取到用户名后，系统自动创建或复用同名内部 `admin_user`。
- 导入、导出、审计日志等仍可保留操作人外键。

如果雷池或上游代理支持额外注入固定密钥头，建议启用：

```env
ABS_AUTH_PROXY_REQUIRED_SECRET_HEADER=X-Auth-Proxy-Secret
ABS_AUTH_PROXY_REQUIRED_SECRET=请替换为随机强密钥
```

后端只有在密钥头匹配时才信任用户名请求头。

## 4. 安全要求

使用 `proxy` 模式时，必须保证本系统后端只能被可信代理访问。

原因是用户名来自请求头，如果用户可以绕过雷池直接访问后端，就可能伪造 `X-Remote-User` 等身份头。

建议：

- 生产环境只暴露雷池入口。
- 本系统 Nginx 或 Backend 不直接暴露到公网或不可信网段。
- 如条件允许，配置 `ABS_AUTH_PROXY_REQUIRED_SECRET_HEADER` 和 `ABS_AUTH_PROXY_REQUIRED_SECRET`。
- 在雷池侧统一清理客户端传入的同名身份头，再由雷池重新注入可信身份头。

## 5. 与本系统审计模型的关系

本系统现有导入、导出、操作批次、审计日志等表依赖 `admin_user.id`。

因此接入统一登录时，不直接删除 `admin_user` 表，而是将外部身份映射为内部管理员用户：

- `disabled` 模式映射到固定用户。
- `proxy` 模式按外部用户名自动映射到同名内部用户。

这样可以取消本地登录体验，同时保留完整审计链路。

## 6. 前端行为

前端会调用 `/api/v1/auth/mode` 判断当前认证模式。

- `local`：显示用户名密码登录表单。
- `disabled` / `proxy`：不显示本地登录表单，访问业务页面时依赖后端 `/api/v1/auth/me` 判断统一认证是否已经生效。

## 7. 后端接口变化

新增接口：

```http
GET /api/v1/auth/mode
```

返回当前认证模式、是否启用本地登录、是否支持本地登出。

原有接口保持：

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `PUT /api/v1/auth/password`

但在 `disabled` / `proxy` 模式下：

- `POST /api/v1/auth/login` 返回本地登录已关闭。
- `PUT /api/v1/auth/password` 返回当前认证模式不支持修改本地管理员密码。

## 8. 部署建议

如果暂时不能确认雷池是否能向源站传递真实用户名，先使用：

```env
ABS_AUTH_MODE=disabled
ABS_AUTH_DISABLED_USERNAME=safeline-admin
```

确认雷池可以传递用户名请求头后，再切换为：

```env
ABS_AUTH_MODE=proxy
ABS_AUTH_PROXY_USER_HEADERS=雷池实际注入的用户名请求头
```

切换后建议检查：

- 访问系统时不再出现本地登录表单。
- `/api/v1/auth/me` 能返回统一登录用户名。
- 审计日志中的操作人符合预期。
- 导入、导出、执行类操作仍能正常写入。

