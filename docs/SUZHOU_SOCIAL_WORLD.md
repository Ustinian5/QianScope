# 苏州 Social World 统一配置

> 归档说明：这是迁移前的苏州兼容配置，不参与贵州默认首页、默认 API 场景或新项目部署。

## 城市口径

- 默认世界：`suzhou_social_world`
- 稳定合成人格原型：5,000
- 加权代表人口：13,047,700
- 人口与行政区口径：`configs/cities/suzhou_2025.json`
- 产品核心地点：南京大学苏州校区

“代表人口”是原型权重之和，不表示系统存储了 13,047,700 个可识别个人，也不表示同量独立 LLM 进程。

## 地图场景

| 场景 ID | 地点 | 产品作用 |
| --- | --- | --- |
| `nju_suzhou` | 南京大学苏州校区 | 首屏核心高亮、L2 校园与 L3 建筑入口 |
| `taihu_science_city` | 太湖科学城 | 创新、就业与通勤网络 |
| `shishan` | 狮山商务区 | 就业、商业与居住交叉 |
| `pingjiang` | 平江历史文化街区 | 公共文化与社区网络 |
| `jinji_lake` | 金鸡湖 | 城市活动、零售与传播 |
| `dushu_lake` | 独墅湖科教创新区 | 高校、科研与青年社区 |
| `taihu_new_city` | 吴中太湖新城 | 家庭、居住、照护与公共服务 |

地图经纬度是为高德地图交互设置的 GCJ-02 显示锚点，不是地籍测量点或建筑边界。苏州校区的官方地址为“苏州市太湖大道 1520 号”；产品中的南雍楼、科创大厦、西区大礼堂和学生食堂只用于合成空间导航，不宣称是建筑级数字孪生。

## 前后端映射

| 后端语义地点 | 前端场景 |
| --- | --- |
| `nju_suzhou_campus`、`campus_teaching`、`campus_library`、`campus_canteen` | `nju_suzhou` |
| `employment_hub`、`transit_network` | `taihu_science_city` |
| `retail_center` | `jinji_lake` |
| `community_center` | `pingjiang` |
| `central_residential` | `taihu_new_city` |
| `north_residential` | `shishan` |

后端返回的人格 `scene_location_id` 必须存在于前端 `WORLD_LOCATIONS`；集成测试负责保证校园预设、人口口径和地点下钻不回退。

## 来源与边界

- [南京大学校区信息](https://www.nju.edu.cn/ysl/)
- [南京大学苏州校区官网](https://njusz.nju.edu.cn/main.htm)
- [南京大学苏州校区地图](https://zcc.nju.edu.cn/dzdt/szxqdt/index.html)
- [2025 年苏州市国民经济和社会发展统计公报](https://tjj.suzhou.gov.cn/sztjj/tjgb/202604/3dc4b574cabd4e86b36ec5d3280e927c.shtml)

人口、人格、关系、日程、当前状态和预测结果均为明确标记的合成原型或授权聚合数据之上的条件估计。
