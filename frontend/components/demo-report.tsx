'use client';

import { useRouter } from 'next/navigation';
import { PredictionResults } from '@/components/prediction-results';
import { demoResult } from '@/lib/demo-result';

export function DemoReport() {
  const router = useRouter();
  return <PredictionResults demo result={demoResult} onNew={() => router.push('/predict')} />;
}
