import type { Metadata } from 'next';
import '@fontsource-variable/manrope/wght.css';
import './globals.css';

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL
  || process.env.SITE_URL
  || (process.env.NODE_ENV === 'production' ? 'https://swm-guizhou.zeabur.app' : 'http://localhost:3000');

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: 'ECHO Social World · 贵阳社会世界',
    template: '%s · ECHO Social World',
  },
  description: '探索贵阳社会世界，让 5,000 个稳定合成人格回答问卷、经历事件并形成可复现的条件预测。',
  keywords: ['Guiyang', 'Guizhou', 'social world model', 'event forecasting', 'survey prediction', 'social simulation', '贵阳', '社会世界', '事件预测'],
  authors: [{ name: 'ECHO-SWM contributors' }],
  applicationName: 'ECHO Social World',
  category: 'research',
  alternates: { canonical: '/' },
  icons: { icon: '/icon.svg', apple: '/icon.png' },
  manifest: '/manifest.webmanifest',
  openGraph: {
    type: 'website',
    locale: 'zh_CN',
    title: 'ECHO 贵阳社会世界',
    description: '在贵阳可交互社会世界中观察人物、关系与事件如何共同演化。',
    siteName: 'ECHO Social World',
    images: [{ url: '/social-world-og-v2.png', width: 1200, height: 630, alt: 'ECHO 贵阳社会世界 · 通用事件预测' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'ECHO 贵阳社会世界',
    description: '贵阳可交互社会世界与通用事件预测',
    images: ['/social-world-og-v2.png'],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
