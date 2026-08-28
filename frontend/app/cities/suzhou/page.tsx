import { AppShell, PageIntro } from '@/components/app-shell';
import { CityWorkbench } from '@/components/city-workbench';

export const metadata = {
  title: '旧版苏州模拟（Legacy）',
  description: '为兼容历史链接保留的旧版苏州城市模拟，不代表当前贵阳社会世界。',
};

export default function SuzhouPage() {
  return (
    <AppShell active="city" title="旧版城市模拟 / 苏州">
      <PageIntro
        eyebrow="LEGACY · SUZHOU WORLD ADAPTER"
        title="旧版苏州城市适配器。"
        description="该页面仅为兼容历史链接而保留；当前比赛项目的主入口与现行模型均为贵阳社会世界。"
      />
      <CityWorkbench />
    </AppShell>
  );
}
