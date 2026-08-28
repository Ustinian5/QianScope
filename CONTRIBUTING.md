# Contributing to ECHO-SWM

感谢参与。项目接受缺陷修复、模型评估、数据契约、前端体验和文档改进。

## 开发流程

1. 从最新主分支创建功能分支。
2. Python 统一使用 Conda 环境；不要直接调用系统 Python。
3. 保持 clean-room 边界：不得提交第三方私有源码、抓取后的受限数据、品牌素材、模型权重或绕过访问控制取得的内容。
4. 新行为必须包含测试；概率、人口、校准或隐私语义变化必须同步更新模型卡或数据卡。
5. 提交前运行完整检查。

```bash
conda create -p ./.conda-env python=3.11 -y
conda run -p ./.conda-env pip install -e '.[dev]'
conda run -p ./.conda-env ruff check .
conda run -p ./.conda-env ruff format --check .
conda run -p ./.conda-env mypy src
conda run -p ./.conda-env pytest

cd frontend
npm ci
npm run check
```

## Pull Request 要求

- 说明问题、解决方式、验证证据和已知限制。
- UI 改动提供桌面与手机截图，并说明键盘操作结果。
- API 改动保持版本兼容，或提供迁移说明。
- 不得把合成结果描述成真实调查，不得把代表人口描述成独立 Agent 数量。
- 涉及真实数据时，必须说明授权、去标识化、保留期限和删除机制。

提交 Contribution 即表示你同意按仓库的 Apache-2.0 许可证提供该贡献。
