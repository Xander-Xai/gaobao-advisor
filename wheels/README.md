# 离线依赖包目录（可选）

CI 和常规构建不需要这个目录：Dockerfile 默认从官方 PyPI 安装
`requirements.lock` 中锁定的依赖。

当构建机没有外网、或到 PyPI 的网络不可靠时，可以先把 wheel 下载到本机，
再让 Docker 构建复用它们：

```bash
pip download -r requirements.lock -d wheels/ --only-binary=:all:
docker build -t gaobao-api .
```

`wheels/` 中除本文件外的内容已被 `.gitignore` 忽略，不要提交任何 wheel。
`--find-links /wheels` 只作为本地缓存使用，构建过程仍然固定使用官方
PyPI 索引，不会替换为第三方镜像源。
