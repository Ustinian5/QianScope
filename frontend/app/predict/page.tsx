import { AppShell } from '@/components/app-shell';
import { PredictionWizard } from '@/components/prediction-wizard';

export const metadata = {
  title: '开始预测',
  description: '通过五步问卷流程预测任意事件的社会反应与未来走向。',
};

export default function PredictPage() {
  return (
    <AppShell active="predict">
      <PredictionWizard />
    </AppShell>
  );
}
