import { AppShell, PageIntro } from '@/components/app-shell';
import { RecentPredictions } from '@/components/recent-predictions';

export const metadata = {
  title: '最近项目',
  description: '查看问卷驱动的通用事件预测项目。',
};

export default function RunsPage() {
  return (
    <AppShell active="runs">
      <PageIntro
        eyebrow="最近项目"
        title="每一次预测，都可以回来继续看。"
        description="打开项目即可查看问卷结果、群体差异、事件发展与不确定范围。"
      />
      <RecentPredictions />
    </AppShell>
  );
}
