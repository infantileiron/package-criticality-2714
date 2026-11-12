# 铎川工务 · 工作包关键路径风险推演

对模拟工务工作包建立零等待 FS 依赖，计算最可能工期 CPM 与独立 Beta-PERT 抽样风险，保留版本快照、复核与 CSV 证据。开工后可在冻结情景上保存带观测时点的进度检查点：已完任务使用实际起止，未开工任务等待前置完成，在途任务按总工期与已耗时推演剩余；迟到更正生成新检查点重算，旧检查点保持可复现。

铎川工务计划组是一个模拟的18人团队。上游来自 `duochuan_workpackage_20261112.json` 的24任务/30条依赖及乐观a、最可能m、悲观b小时数。原先用电子表格把工时相加：并行关系漏算，关键路径变化不可见，截止期比例没有概率模型口径。本项目承接工作包校验、依赖建模、冻结情景、后台推演到人工复核；下游是交付负责人的计划复核稿，不直接安排真实人员设备或承诺交付。

## 一天的计划复核

1. 09:00 计划员核对「检修通道加固工作包」24个具名任务与三点工期。
2. 09:05 检查现场交接、区域围护、并行施工、联合复检等30条零等待FS关系，保留独立备件盘点任务。
3. 09:10 选择32小时截止期、1500样本与固定seed=2410，冻结任务/边/三点范围的情景v1。
4. 09:15 提交Redis队列，由独立worker计算最可能工期基线与每次独立工期抽样。
5. 09:20 查看24小时CPM基线，核对ES/EF/LS/LF/总时差与关键连接。
6. 09:25 查看完工样本分布、分位数、达标次数/分母及逐任务关键次数。
7. 09:30 写明独立工期、资源/天气共因未建模等边界，提交接受或待补充复核版本。
8. 09:40 负责人批准最新接受版本，下载逐任务CSV；后续新增依赖只进入新情景，不改写旧快照。
9. 开工后 09:20 起在「进度检查点」页录入观测时点与各任务状态：已完填实际起止，在途填实际开始，未开工留空等待前置。后台按该切面重算完工分布、达标率与关键任务；原情景运行与批准报告只读保留。

## 快速启动

```sh
cp .env.example .env
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 180
# 自动seed也可显式复跑；仅插入缺少的自然键，不覆盖用户修改
docker compose exec backend python -m scripts.seed_demo
```

前端 `http://localhost:18239`，API文档 `http://localhost:19239/docs`，MySQL `localhost:17739`。演示密码均为 `Schedule2026!`。

| 角色 | 账号 | 权限与典型动作 |
|---|---|---|
| analyst | analyst@duochuan.demo | 导入工作包、添加FS边、冻结情景、提交运行与交付复核 |
| admin | admin@duochuan.demo | 全部计划功能，批准最新接受复核版本归档 |
| viewer | viewer@duochuan.demo | 读取结果/审计，下载已批准CSV；无写入或批准权限 |

进度检查点沿用同一角色控制：analyst/admin 可录入与更正，viewer 只读。演示数据含一条 `demo-scenario` 的 09:20 检查点（T01–T04 已完、T05–T08 在途）。

后端JWT真实控制角色权限；审计保存写入及拒绝状态；全局错误中间件与输入异常处理返回可恢复错误。演示密钥和凭据只供本地模拟环境。

## 算法口径

`backend/src/services/cpm.py::cpm(durations, edges, tolerance=1e-8)` 接收任务ID→非负有限小时数与有向依赖对。按稳定ID拓扑排序，ES取所有前置EF的最大值，EF=ES+工期；项目完工=max(EF)。反向LF取后继LS的最小值，无后继取**本次项目实际完工**；LS=LF−工期，总时差=LS−ES。共同零起点与共同实际完工边界等价于连接所有起点/终点的虚拟源汇，孤立任务同时受两边界约束。输出全量前后向时刻、关键任务/连接、拓扑序、源汇任务与容差。未知端点、自环、重复边、环和负/非有限工期拒绝。

基线用最可能m工期。外部deadline从不参与CPM或LF，因此改变截止期只影响达标比例。关键任务总时差≤1e-8小时，微小浮点时差归零；关键连接还须前置EF与后续ES相接，不能只凭两个端点均关键就高亮旁路边。

`backend/src/services/pert.py::simulate(tasks, edges, samples, seed, deadline)` 采用相互独立的Beta-PERT，λ=4：

- a≤m≤b，a=m=b为点质量，不调用Beta采样。
- 非常数 `alpha=1+4(m-a)/(b-a)`，`beta=1+4(b-m)/(b-a)`；工期为 `a+(b-a)*Beta(alpha,beta)`。
- 每次重新执行完整CPM，依赖按最大前置完工处理，LF仍以该次实际项目完工为基准。
- 关键度=该任务总时差≤1e-8小时的次数/全部样本数；不把基线关键集合套到每次模拟。
- 达标比较为 `finish <= deadline + 1e-8小时`；明确微小容差处理0.1+0.2+0.3等浮点边界，超过容差仍不达标。结果/页面/CSV公开deadline_tolerance_hours。
- 保存全部完工样本、直方图、达标次数、分母、seed及p05/p50/p80/p95；分位采用(n−1)q位置线性插值。有限样本比例不是交付保证。

随机数来自标准库固定seed，任务按ID排序抽样，输入重排不改变序列。只支持零等待FS，不含日历、资源占用、共享天气或人员共因，也不是资源约束排程。

### 进度检查点口径

`backend/src/services/progress.py` 在冻结情景上接收观测时点 `observation_time`（自项目开工计小时）与逐任务进度：

- **已完任务**固定为实际区间 `[actual_start, actual_finish]`，基线工期=实际完成−实际开始；不进入抽样。未填写的任务按未开工处理。
- **在途任务**需实际开始且不得填实际完成。已耗时=观测时点−实际开始；总工期在已耗时之后做 Beta-PERT 条件抽样（只接受总工期≥已耗时，最多64次尝试），工期=max(已耗时, 总工期)，剩余=总工期−已耗时。已耗时超过悲观 b、或条件尝试耗尽时按已耗时收口并计入 `conditional_fallback_samples`。
- **未开工任务**以观测时点为释放时点，并等待所有前置的实际/推演完成；`cpm_with_release` 令 ES=max(前置EF, 释放时点)，LF 仍取该次实际项目完工。
- **拒绝**：观测时点为负/非有限；已完完成早于开始或晚于观测时点；在途开始晚于观测时点或已耗时超过悲观 b；未开工却填写实际起止；情景外任务或重复任务；任一已开工任务的前置未完成或前置实际完成晚于其实际开始（违反FS依赖）。
- **达标与分布**：每次抽样重算CPM，完工样本自项目开工计，不是从观测时点重新计时；达标为完工≤deadline+1e-8h。deadline 为绝对外部时点，若已早于观测时点，如实给出0达标并标记 `deadline_passed_at_observation`，不视为进度矛盾。
- **复现与更正**：检查点保存完整进度、情景快照与 SHA256 校验和（含观测时点、样本、seed、deadline）；相同输入复现相同校验和与完工样本。迟到更正必须指向同情景已完成的原始检查点、保持原观测时点，生成新的 `sequence` 并重算；不得在更正记录上继续叠加。旧检查点内容、结果与校验和不变。

## 实体、技术与目录

七实体 WorkPackage、TaskDependency、DurationScenario、ScheduleRun、ProgressCheckpoint、DeliveryReview、Report，贯穿model/schema/service/route、前端API/store与领域页。情景按工作包版本化并冻结完整任务和边；运行保存结果/校验和；进度检查点在情景快照上版本化并保存结果/校验和，场景结果与报告不被改写；复核新增不可变版本；归档绑定接受复核ID，后续待补充版本不修改旧CSV。

| 部分 | 技术 |
|---|---|
| 前端 | Vue3、TypeScript、Vite、真实SVG DAG/直方图与关键度 |
| API | Python3.11、FastAPI、SQLAlchemy、JWT |
| 后台 | Redis真实队列（运行与检查点两队列）、独立Python worker及心跳检查 |
| 数据库 | MySQL8.4，deadline为DOUBLE、计数/seed为INTEGER |
| Docker | 恰好frontend/backend/worker/db/redis五服务，全部真实健康检查 |

`frontend/src` 分api/stores/types/components/common/hooks/pages/router/utils/constants；七领域页加登录（含进度检查点页），DAG、风险摘要、情景条跨页共享。`backend/src` 分models/schemas/services/controllers/routes/middlewares/utils/constants/config，seed在 `backend/scripts/seed_demo.py`，初始schema说明在 `backend/migrations`。测试、截图和报告仅在批根 `test-artifacts/gb-2410`。依赖使用匹配package/lock执行npm ci，没有替换依赖名称。

`.env.example` 包含COMPOSE_PROJECT_NAME=package-criticality、FRONTEND_PORT=18239、BACKEND_PORT=19239、DB_PORT=17739、SEED_DEMO=true、JWT_SECRET；DATABASE_URL/REDIS_URL由compose注入。数据库、Redis、worker产物为三个命名卷，Nginx代理 `/api/` 并做SPA回落，健康检查使用127.0.0.1。本地开发前端 `npm ci && npm run dev`，API `uvicorn src.main:app --host 0.0.0.0`，worker `python -m src.worker`，需配置可连接的数据库/Redis地址。

共享枚举 role、run_status、review_decision、dependency_type、progress_status 位于 `backend/src/constants/enums.py` 和 `frontend/src/constants/enums.ts`；schema Literal、状态服务和只允许FS的依赖接口共同约束实际取值。

## 已知边界与清理

最多60个任务、后台100至5000样本；进度检查点与运行共用情景的样本数/seed/deadline；JSON表单导入，后续修改通过新工作包或新情景，不覆盖已冻结范围。完整DAG可局部横向滚动，节点ID、m工期、ES→EF与关键线同表核对。单worker未实现生产级分布式租约；初始SQLAlchemy建表不含生产迁移回滚；无多租户隔离。模拟范围和独立工期假设不代表真实工期分布。

```sh
docker compose down -v --remove-orphans
```

后端单元测试（不依赖数据库/Redis）：`cd backend && python3 tests/test_progress.py`。

License: MIT。所有工作包、任务和工期为模拟数据。
