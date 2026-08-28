import { AppShell } from '@/components/app-shell';
import { DemoReport } from '@/components/demo-report';

export const metadata = {
  title: '示例预测报告',
  description: '查看黔镜 QianScope 的问卷预测、群体差异与未来事件反应路径示例。',
};

export default function DemoPage() {
  return (
    <AppShell active="overview">
      <DemoReport />
    </AppShell>
  );
}
