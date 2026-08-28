export type WorldLevel = 'city' | 'campus' | 'interior';

export type WorldSceneIdentity = {
  signature: string;
  architecture: string;
  atmosphere: 'conference-glow' | 'innovation-glow' | 'campus-rain' | 'river-mist' | 'heritage-mist' | 'transit-glow' | 'neighborhood-sun';
  status: string;
  landmarks: Array<{ label: string; left: number; top: number; world?: [number, number, number] }>;
};

export type WorldLocation = {
  id: string;
  name: string;
  short: string;
  description: string;
  kind: 'campus' | 'park' | 'retail' | 'residential' | 'apartment';
  x: number;
  y: number;
  longitude: number;
  latitude: number;
  population: string;
  featured?: boolean;
  focusRotation?: number;
  labelOffset?: [number, number];
  buildings?: [string, string, string, string];
  scene: WorldSceneIdentity;
};

export const SOCIAL_WORLD_CITY = {
  id: 'guiyang',
  name: '贵阳',
  fullName: '贵阳市',
  representedPopulation: 6_668_900,
  representedPopulationLabel: '666.89 万',
  prototypeCount: 5_000,
  heroLocationId: 'guiyang_convention',
  defaultBuilding: '国际会议中心',
} as const;

export type WorldAgent = {
  id: string;
  name: string;
  role: string;
  organization: string;
  locationId: string;
  location: string;
  bio: string;
  traits: string[];
  values: string[];
  goal: string;
  action: string;
  mood: string;
  stress: number;
  intention: number;
  memories: string[];
  relationships: Array<{ agentId: string; relation: string; trust: number; name?: string; role?: string }>;
  x: number;
  y: number;
  backendId?: string;
  representedWeight?: number;
  profileHash?: string;
  profileCompleteness?: number;
  definitionVersion?: string;
  demographics?: Record<string, string>;
  frameworks?: PersonaProfileFramework[];
};

export type PersonaProfileFramework = {
  id: string;
  label: string;
  reference: string;
  description: string;
  dimensions: Array<{
    key: string;
    label: string;
    description: string;
    score: number;
    scaleMin: number;
    scaleMax: number;
    lowPole: string;
    highPole: string;
    interpretation: string;
  }>;
};

export type ToolKey =
  | 'survey'
  | 'event'
  | 'marketing'
  | 'trend'
  | 'brand'
  | 'product'
  | 'demand'
  | 'pricing'
  | 'competitive'
  | 'funnel'
  | 'churn'
  | 'creator';

export type ToolDefinition = {
  key: ToolKey;
  icon: string;
  label: string;
  description: string;
  group: 'simulation' | 'insight';
};

export const WORLD_LOCATIONS: WorldLocation[] = [
  {
    id: 'guiyang_convention', name: '贵阳国际会议展览中心', short: '贵阳会展', description: '会展客流、数博发布、商务交流与观山湖城市生活交叠的高活性节点。', kind: 'retail', x: 54, y: 24, longitude: 106.645753, latitude: 26.642233, population: '48,600', featured: true, focusRotation: -12, labelOffset: [-54, 8], buildings: ['国际会议中心', '展览中心登录厅', '数博发布厅', '城市会客厅'],
    scene: { signature: '会展轴线 · 数博舞台 · 城市客厅', architecture: '现代山地会展综合体', atmosphere: 'conference-glow', status: '452 个会展活动体 · 参会、发布与商务动线', landmarks: [{ label: '会展广场', left: 55, top: 67, world: [5, .7, 2.6] }, { label: '数博发布厅', left: 71, top: 57, world: [-8.2, 2.75, -.8] }, { label: '国际会议中心', left: 48, top: 30, world: [3.65, 10.4, -9] }, { label: '城市会客厅', left: 31, top: 55, world: [12, .8, 6.5] }] },
  },
  {
    id: 'guiyang_big_data', name: '贵阳大数据科创城', short: '大数据科创城', description: '数据企业、科研团队、创业者与青年人才共同形成的贵阳贵安创新协作区。', kind: 'apartment', x: 18, y: 65, longitude: 106.500494, latitude: 26.467112, population: '31,800', focusRotation: -18, labelOffset: [-58, 32], buildings: ['科创城展示中心', '数据要素路演厅', '算力协同实验室', '青年人才社区'],
    scene: { signature: '数智塔楼 · 算力协同 · 青年创客', architecture: '开放式数据科创园区', atmosphere: 'innovation-glow', status: '286 个科创活动体 · 研发、路演与通勤动线', landmarks: [{ label: '数智中庭', left: 47, top: 48, world: [6.2, .75, -3.6] }, { label: '算力连廊', left: 68, top: 36, world: [0, 1.9, 7.3] }, { label: '接驳站', left: 30, top: 65, world: [-2.8, .75, 1.4] }, { label: '数据要素实验平台', left: 72, top: 66, world: [15.5, 7.9, -7.4] }] },
  },
  {
    id: 'guizhou_university', name: '贵州大学西校区', short: '贵大西校区', description: '学习、科研、社团与校园服务相互连接的青年社会世界。', kind: 'campus', x: 57, y: 71, longitude: 106.655275, latitude: 26.449375, population: '36,200', focusRotation: -9, labelOffset: [52, 28], buildings: ['西区图书馆', '工程训练中心', '大学生活动中心', '学生食堂'],
    scene: { signature: '山地校园 · 学术绿轴 · 青年活力', architecture: '开放式山地大学校园', atmosphere: 'campus-rain', status: '720 个校园活动体 · 教学、科研与生活动线', landmarks: [{ label: '贵州大学西校区', left: 50, top: 25, world: [0, 3.2, 15.2] }, { label: '校园绿轴', left: 48, top: 57, world: [-.2, .55, 6.8] }, { label: '明俊湖', left: 59, top: 47, world: [8.6, .48, 2.7] }, { label: '田径运动场', left: 19, top: 52, world: [-15.6, .48, 9.2] }, { label: '学术广场', left: 47, top: 39, world: [-.4, .58, 2.8] }, { label: '校史文化点', left: 50, top: 62, world: [-.3, 2.25, 8.9] }, { label: '教学组团', left: 72, top: 68, world: [12.3, 5.2, 9.1] }, { label: '创新连廊', left: 63, top: 35, world: [7.2, 4.95, -9.6] }, { label: '学生生活区', left: 28, top: 65, world: [-7.1, 3.4, 8.2] }, { label: '湖畔步道', left: 65, top: 56, world: [11.2, .65, 4.2] }] },
  },
  {
    id: 'jiaxiu_tower', name: '甲秀楼·南明河', short: '甲秀楼', description: '历史地标、滨河公共空间、游客与本地市民持续交汇的城市文化界面。', kind: 'park', x: 75, y: 50, longitude: 106.719721, latitude: 26.571358, population: '42,300', focusRotation: 8, labelOffset: [46, -32], buildings: ['甲秀楼文化展厅', '翠微园', '南明河公共驿站', '河滨书屋'],
    scene: { signature: '楼桥水岸 · 山城夜色 · 市井相逢', architecture: '传统楼阁与滨河街区', atmosphere: 'river-mist', status: '236 个滨河活动体 · 居民、游客与文化动线', landmarks: [{ label: '南明河', left: 51, top: 49, world: [0, .55, 1.5] }, { label: '浮玉桥', left: 48, top: 61, world: [0, 1.18, 3.2] }, { label: '甲秀楼', left: 67, top: 57, world: [5.1, .72, 5] }, { label: '翠微园', left: 29, top: 42, world: [-10.2, 2.05, -3] }] },
  },
  {
    id: 'qingyan_town', name: '青岩古镇', short: '青岩古镇', description: '古镇居民、非遗商户、游客与社区治理共同作用的文旅社会现场。', kind: 'park', x: 68, y: 86, longitude: 106.686834, latitude: 26.331095, population: '27,900', focusRotation: 14, labelOffset: [48, 30], buildings: ['古镇游客中心', '非遗工坊', '背街社区议事厅', '状元文化书屋'],
    scene: { signature: '石巷城墙 · 非遗烟火 · 文旅共生', architecture: '明清山地古镇街巷', atmosphere: 'heritage-mist', status: '264 个古镇活动体 · 居民、商户与游客动线', landmarks: [{ label: '定广门', left: 29, top: 42, world: [-10.2, 2.05, -2.9] }, { label: '青石主街', left: 51, top: 49, world: [0, .55, 1.5] }, { label: '非遗工坊', left: 67, top: 57, world: [5.1, .72, 5] }, { label: '背街社区', left: 48, top: 61, world: [10.4, 2.05, 3.9] }] },
  },
  {
    id: 'guiyang_north_station', name: '贵阳北站', short: '贵阳北站', description: '高铁、地铁、公交、网约车与跨城旅客密集换乘的区域交通枢纽。', kind: 'retail', x: 62, y: 32, longitude: 106.674554, latitude: 26.619478, population: '56,800', focusRotation: -4, labelOffset: [54, -12], buildings: ['综合换乘大厅', '高铁候车厅', '公交调度中心', '旅客服务中心'],
    scene: { signature: '高铁门户 · 立体换乘 · 流动人群', architecture: '山地立体综合交通枢纽', atmosphere: 'transit-glow', status: '518 个枢纽活动体 · 到达、换乘与疏散动线', landmarks: [{ label: '高铁站房', left: 51, top: 48, world: [7, 13.6, -9.5] }, { label: '轨交换乘厅', left: 31, top: 59, world: [-1.8, 1.1, 2.2] }, { label: '北广场', left: 67, top: 36, world: [8.7, 1.8, 7.6] }, { label: '公交接驳区', left: 72, top: 68, world: [16.8, 7.8, 8.4] }] },
  },
  {
    id: 'huaguoyuan', name: '花果园社区', short: '花果园', description: '超大居住社区中的通勤、家庭照护、商业服务与基层治理共同演化。', kind: 'residential', x: 64, y: 53, longitude: 106.687582, latitude: 26.566334, population: '68,400', focusRotation: 5, labelOffset: [-52, 34], buildings: ['社区服务中心', '湿地公园驿站', '托育活动站', '健康管理中心'],
    scene: { signature: '高密住区 · 立体通勤 · 邻里互助', architecture: '山地高密度完整社区', atmosphere: 'neighborhood-sun', status: '428 个社区活动体 · 居住、照护与公共服务动线', landmarks: [{ label: '社区客厅', left: 47, top: 49, world: [5.5, 2.85, -5.3] }, { label: '儿童活动场', left: 31, top: 62, world: [-4.8, 2.1, 3.8] }, { label: '湿地公园步道', left: 67, top: 68, world: [0, .72, 8.6] }, { label: '邻里服务站', left: 71, top: 43, world: [11.5, .75, 4.8] }] },
  },
];

export const WORLD_AGENTS: WorldAgent[] = [
  {
    id: 'agent_zhou_qihang', name: '周启航', role: '会展现场运行经理', organization: '贵阳国际会议展览中心运营团队', locationId: 'guiyang_convention', location: '国际会议中心登录大厅',
    bio: '熟悉大型会展的进出场节奏，习惯把安保、交通和参会体验放在同一张运行图上。',
    traits: ['高尽责', '冷静', '系统思考'], values: ['安全', '效率', '协作'], goal: '让大型活动高峰平稳散场。', action: '核对闭馆后的分区疏散方案', mood: '专注', stress: 61, intention: 82,
    memories: ['上次雨天散场时网约车上客区短时排队。', '陈雨棠建议把观众提示提前到闭馆前四十分钟。'],
    relationships: [{ agentId: 'agent_chen_yutang', relation: '活动协作方', trust: .84 }, { agentId: 'agent_zheng_yuan', relation: '交通联络人', trust: .78 }], x: 43, y: 47,
  },
  {
    id: 'agent_chen_yutang', name: '陈雨棠', role: '数字产业活动策划人', organization: '贵阳数博活动策划工作室', locationId: 'guiyang_convention', location: '数博发布厅',
    bio: '擅长把技术议题转化为公众可理解的活动内容，同时警惕只追求传播声量。',
    traits: ['外向', '创造性', '风险敏感'], values: ['参与', '真实', '责任'], goal: '完成一场兼顾行业深度与公众体验的数智主题活动。', action: '复核发布厅观众动线和直播节点', mood: '期待', stress: 55, intention: 80,
    memories: ['上午的彩排显示入口说明仍不够清楚。', '周启航确认了闭馆后的地铁接驳窗口。'],
    relationships: [{ agentId: 'agent_zhou_qihang', relation: '场地协作方', trust: .85 }, { agentId: 'agent_luo_xiao', relation: '参展创业者', trust: .69 }], x: 61, y: 39,
  },
  {
    id: 'agent_lin_rui', name: '林芮', role: '数据工程师', organization: '贵州数智场景实验室', locationId: 'guiyang_big_data', location: '算力协同实验室',
    bio: '负责把多源数据接入真实业务场景，强调数据最小化、可追溯与结果复核。',
    traits: ['严谨', '独立', '高开放'], values: ['证据', '隐私', '可靠'], goal: '完成一套可审计的城市事件数据管道。', action: '检查算力任务的异常日志', mood: '投入', stress: 49, intention: 84,
    memories: ['一次字段口径偏差曾让模型结论发生明显变化。', '杜晓月提醒团队补充公众沟通说明。'],
    relationships: [{ agentId: 'agent_du_xiaoyue', relation: '治理评审伙伴', trust: .82 }, { agentId: 'agent_luo_xiao', relation: '产品协作方', trust: .74 }], x: 44, y: 55,
  },
  {
    id: 'agent_luo_xiao', name: '罗骁', role: '创业团队产品负责人', organization: '贵阳大数据科创城创业社区', locationId: 'guiyang_big_data', location: '数据要素路演厅',
    bio: '重视一线用户信号，也会警惕样本偏差和技术概念带来的过度承诺。',
    traits: ['外向', '目标导向', '适度怀疑'], values: ['创造', '影响力', '成长'], goal: '验证中小企业是否真正需要新的算力服务。', action: '整理路演后的用户访谈', mood: '期待', stress: 46, intention: 78,
    memories: ['上一个项目因只访谈早期用户而高估需求。', '林芮建议先明确数据授权边界。'],
    relationships: [{ agentId: 'agent_lin_rui', relation: '技术协作方', trust: .75 }, { agentId: 'agent_chen_yutang', relation: '活动策划伙伴', trust: .68 }], x: 60, y: 44,
  },
  {
    id: 'agent_du_xiaoyue', name: '杜晓月', role: '数字治理研究员', organization: '贵阳数据治理观察组', locationId: 'guiyang_big_data', location: '科创城展示中心',
    bio: '关注技术应用对企业、市民和公共服务的差异化影响，倾向先厘清责任边界再评价效果。',
    traits: ['审慎', '高同理心', '分析性'], values: ['公平', '透明', '公共性'], goal: '形成一份可执行的数据应用风险清单。', action: '访谈入驻企业与园区服务人员', mood: '沉思', stress: 38, intention: 73,
    memories: ['部分小企业不清楚算力补贴的申请条件。', '林芮完整记录了数据处理链路。'],
    relationships: [{ agentId: 'agent_lin_rui', relation: '长期评审伙伴', trust: .83 }, { agentId: 'agent_luo_xiao', relation: '调研对象', trust: .66 }], x: 72, y: 61,
  },
  {
    id: 'agent_wang_zhixia', name: '王知夏', role: '新闻传播专业本科生', organization: '贵州大学', locationId: 'guizhou_university', location: '西区图书馆',
    bio: '关注校园公共议题，习惯核实来源后再表达立场，正在记录青年如何理解城市科技议题。',
    traits: ['开放', '谨慎表达', '高同理心'], values: ['公平', '自主', '真实'], goal: '完成一组不简化受访者的校园观察。', action: '整理有关校园夜间服务的采访笔记', mood: '专注', stress: 41, intention: 74,
    memories: ['未经核实的群聊截图曾引发不必要的争论。', '何嘉答应提供服务调整的完整说明。'],
    relationships: [{ agentId: 'agent_he_jia', relation: '采访对象', trust: .64 }, { agentId: 'agent_li_chuan', relation: '课程伙伴', trust: .77 }], x: 42, y: 44,
  },
  {
    id: 'agent_li_chuan', name: '黎川', role: '计算机科学硕士生', organization: '贵州大学', locationId: 'guizhou_university', location: '工程训练中心',
    bio: '对社会仿真和效率工具保持兴趣，倾向通过可复现实验而非群体声量形成判断。',
    traits: ['好奇', '独立', '低从众'], values: ['创新', '能力', '自由'], goal: '完成面向山地城市的群体仿真课程项目。', action: '调试地点传播参数', mood: '投入', stress: 53, intention: 85,
    memories: ['上次实验发现问卷措辞显著改变选择分布。', '计划邀请不同专业的同学进行盲测。'],
    relationships: [{ agentId: 'agent_wang_zhixia', relation: '课程伙伴', trust: .78 }, { agentId: 'agent_lin_rui', relation: '校外技术导师', trust: .7 }], x: 64, y: 51,
  },
  {
    id: 'agent_he_jia', name: '何嘉', role: '校园服务协调员', organization: '贵州大学西校区', locationId: 'guizhou_university', location: '大学生活动中心',
    bio: '熟悉校园运营约束，希望学生能看到决策依据，也对突发舆情保持谨慎。',
    traits: ['负责', '克制', '善于协调'], values: ['秩序', '照顾', '稳定'], goal: '在有限资源下提高夜间校园服务可达性。', action: '核对活动场地与安保排班', mood: '平静', stress: 58, intention: 67,
    memories: ['学生对信息不透明的反应常强于调整本身。', '王知夏主动核对了服务公告原文。'],
    relationships: [{ agentId: 'agent_wang_zhixia', relation: '校园沟通伙伴', trust: .72 }, { agentId: 'agent_li_chuan', relation: '学生项目联系人', trust: .69 }], x: 73, y: 64,
  },
  {
    id: 'agent_zhao_shouan', name: '赵守安', role: '城市文化讲解员', organization: '甲秀楼文化志愿团队', locationId: 'jiaxiu_tower', location: '甲秀楼文化展厅',
    bio: '长期讲述甲秀楼与南明河的城市记忆，反对把历史地标简化成打卡背景。',
    traits: ['耐心', '温和', '守信'], values: ['传承', '尊重', '公共性'], goal: '让游客理解地标与贵阳日常生活的连接。', action: '准备傍晚的滨河讲解', mood: '从容', stress: 31, intention: 72,
    memories: ['雨后游客更愿意在桥边停留听完整讲解。', '唐澜正在试验新的滨河慢行提示。'],
    relationships: [{ agentId: 'agent_tang_lan', relation: '公共空间协作方', trust: .88 }], x: 43, y: 56,
  },
  {
    id: 'agent_tang_lan', name: '唐澜', role: '滨河公共空间管理员', organization: '南明河公共空间服务团队', locationId: 'jiaxiu_tower', location: '浮玉桥东侧',
    bio: '每天观察居民、游客与慢跑者如何共享河岸，偏好用小步试验化解通行冲突。',
    traits: ['细致', '克制', '合作'], values: ['安全', '可达', '秩序'], goal: '在夜游热度上升时保持滨河空间连续可达。', action: '巡查浮玉桥与河滨步道', mood: '稳定', stress: 43, intention: 66,
    memories: ['周末傍晚浮玉桥东侧最容易形成短暂停留。', '赵守安建议把讲解集合点移出主通道。'],
    relationships: [{ agentId: 'agent_zhao_shouan', relation: '文化活动协作方', trust: .87 }, { agentId: 'agent_an_ran', relation: '城市观察联系人', trust: .65 }], x: 59, y: 49,
  },
  {
    id: 'agent_lu_qinghe', name: '陆清禾', role: '非遗工坊主理人', organization: '青岩古镇青年手作社', locationId: 'qingyan_town', location: '青石主街非遗工坊',
    bio: '在传统技艺传承与游客体验之间寻找平衡，对同质化商业内容保持克制。',
    traits: ['温和', '审慎开放', '高尽责'], values: ['传承', '社区', '真实'], goal: '让工坊可持续经营且保留地方生活感。', action: '整理今天的手作体验预约', mood: '平静', stress: 36, intention: 70,
    memories: ['节假日短时客流会挤压熟客的日常空间。', '石遥愿意把住客错峰建议写进入住提示。'],
    relationships: [{ agentId: 'agent_shi_yao', relation: '古镇邻里', trust: .86 }, { agentId: 'agent_zhao_shouan', relation: '文化交流伙伴', trust: .72 }], x: 41, y: 57,
  },
  {
    id: 'agent_shi_yao', name: '石遥', role: '古镇民宿经营者', organization: '青岩背街社区', locationId: 'qingyan_town', location: '背街社区议事厅附近',
    bio: '熟悉游客决策与居民日常之间的摩擦，会把订单变化和邻里反馈一起考虑。',
    traits: ['务实', '社交敏锐', '主动'], values: ['互惠', '稳定', '邻里'], goal: '在旅游旺季保持经营收益与社区安宁。', action: '更新周末住客的交通与游览提示', mood: '忙碌', stress: 52, intention: 71,
    memories: ['部分住客会根据短视频推荐集中到同一条巷子。', '陆清禾的工坊预约能有效分散停留时段。'],
    relationships: [{ agentId: 'agent_lu_qinghe', relation: '经营互助伙伴', trust: .87 }, { agentId: 'agent_jiang_wenlin', relation: '社区治理交流', trust: .64 }], x: 58, y: 49,
  },
  {
    id: 'agent_zheng_yuan', name: '郑远', role: '综合交通调度员', organization: '贵阳北站枢纽协同团队', locationId: 'guiyang_north_station', location: '公交调度中心',
    bio: '在高铁到达波次中协调地铁、公交和出租运力，习惯用最坏情景检验预案。',
    traits: ['果断', '高尽责', '风险敏感'], values: ['安全', '准点', '协作'], goal: '降低集中到站时的换乘等待和信息盲区。', action: '对照晚高峰列车到达波次配置运力', mood: '警觉', stress: 69, intention: 83,
    memories: ['强降雨时部分旅客会临时转向网约车。', '周启航提前同步了会展散场时间。'],
    relationships: [{ agentId: 'agent_zhou_qihang', relation: '会展交通联络人', trust: .8 }, { agentId: 'agent_an_ran', relation: '旅客反馈渠道', trust: .7 }], x: 48, y: 46,
  },
  {
    id: 'agent_an_ran', name: '安然', role: '城市通勤观察者', organization: '贵阳青年城市观察社', locationId: 'guiyang_north_station', location: '综合换乘大厅',
    bio: '长期记录高铁旅客和本地通勤者的换乘体验，善于把零散反馈整理成问题路径。',
    traits: ['敏锐', '高同理心', '独立'], values: ['可达', '准确', '服务'], goal: '形成一份面向首次到访者的换乘障碍地图。', action: '记录到达层指引与旅客问询', mood: '投入', stress: 37, intention: 76,
    memories: ['首次到访者常在地铁入口与网约车区之间犹豫。', '郑远根据旅客反馈调整过临时引导牌。'],
    relationships: [{ agentId: 'agent_zheng_yuan', relation: '调研协作方', trust: .73 }, { agentId: 'agent_tang_lan', relation: '城市观察联系人', trust: .66 }], x: 64, y: 61,
  },
  {
    id: 'agent_chen_qiao', name: '陈乔', role: '社区全科医生', organization: '花果园社区健康服务站', locationId: 'huaguoyuan', location: '健康管理中心',
    bio: '关注高密社区家庭在通勤、照护和健康之间的真实负担，偏好可持续的小规模干预。',
    traits: ['高同理心', '稳健', '直接'], values: ['健康', '公平', '可及'], goal: '提高居民在强降雨和高温时获得健康支持的便利度。', action: '结束家访后核对重点居民清单', mood: '温和', stress: 47, intention: 78,
    memories: ['不少上班族不知道周末也能预约咨询。', '蒋文林正在更新独居长者联络表。'],
    relationships: [{ agentId: 'agent_jiang_wenlin', relation: '社区协作伙伴', trust: .87 }, { agentId: 'agent_song_ke', relation: '家庭健康联系人', trust: .82 }], x: 56, y: 53,
  },
  {
    id: 'agent_song_ke', name: '宋可', role: '产品设计师与年轻家长', organization: '花果园居民互助小组', locationId: 'huaguoyuan', location: '托育活动站',
    bio: '亲自经历接送、通勤与社区服务流程，常用服务设计方法表达年轻家庭需求。',
    traits: ['开放', '务实', '主动'], values: ['家庭', '自主', '友好'], goal: '让托育、交通和应急信息更适合双职工家庭。', action: '陪孩子等待家人并测试社区通知小程序', mood: '放松', stress: 42, intention: 72,
    memories: ['暴雨天从停车区到托育站的路线不够连续。', '陈乔解释了新的家庭健康预约方式。'],
    relationships: [{ agentId: 'agent_chen_qiao', relation: '家庭医生', trust: .85 }, { agentId: 'agent_jiang_wenlin', relation: '社区提案伙伴', trust: .79 }], x: 39, y: 63,
  },
  {
    id: 'agent_jiang_wenlin', name: '蒋文林', role: '社区网格协调员', organization: '花果园社区服务中心', locationId: 'huaguoyuan', location: '社区服务中心',
    bio: '熟悉楼栋、商户与物业之间的信息路径，面对突发情况会优先确认脆弱人群与现场执行能力。',
    traits: ['负责', '耐心', '行动导向'], values: ['互助', '公平', '可靠'], goal: '让预警信息真正抵达需要帮助的居民。', action: '更新强降雨响应联络树', mood: '专注', stress: 59, intention: 84,
    memories: ['只在大群发布通知会漏掉部分长者。', '宋可帮助把专业预警改写成了家庭行动清单。'],
    relationships: [{ agentId: 'agent_chen_qiao', relation: '社区健康协作方', trust: .88 }, { agentId: 'agent_song_ke', relation: '居民提案伙伴', trust: .8 }, { agentId: 'agent_shi_yao', relation: '社区治理交流', trust: .63 }], x: 67, y: 45,
  },
];

export const WORLD_TOOLS: ToolDefinition[] = [
  { key: 'survey', icon: '▤', label: '问卷调查', description: '让稳定人格原型回答一个问题', group: 'simulation' },
  { key: 'event', icon: 'ϟ', label: '事件推演', description: '注入事件并观察传播与反应', group: 'simulation' },
  { key: 'marketing', icon: '⌁', label: '营销活动模拟', description: '模拟一次活动的传播和反应', group: 'insight' },
  { key: 'trend', icon: '⌁', label: '趋势探测', description: '估算话题关注度与触达', group: 'insight' },
  { key: 'brand', icon: '◉', label: '品牌洞察', description: '观察印象、情绪与推荐意愿', group: 'insight' },
  { key: 'product', icon: '✣', label: '产品洞察', description: '让居民为功能优先级投票', group: 'insight' },
  { key: 'demand', icon: '✓', label: '模拟需求信号', description: '用问卷观察合成需求信号', group: 'insight' },
  { key: 'pricing', icon: '¥', label: '定价测试', description: '扫描价格、需求和营收指数', group: 'insight' },
  { key: 'competitive', icon: '◆', label: '竞品反应', description: '生成对手画像与应对动作', group: 'insight' },
  { key: 'funnel', icon: '▽', label: '转化漏斗', description: '推演认知到行动的逐层转化', group: 'insight' },
  { key: 'churn', icon: '∩', label: '流失预测', description: '预测变化造成的用户流失', group: 'insight' },
  { key: 'creator', icon: '◎', label: '达人智配', description: '为传播任务匹配合适节点', group: 'insight' },
];

export function stableUnit(seedText: string, offset = 0) {
  let seed = 2166136261 + offset;
  for (let index = 0; index < seedText.length; index += 1) {
    seed ^= seedText.charCodeAt(index);
    seed = Math.imul(seed, 16777619);
  }
  return ((seed >>> 0) % 10000) / 10000;
}
