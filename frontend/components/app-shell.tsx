import type { ReactNode } from 'react';
import Link from 'next/link';

type NavKey = 'overview' | 'predict' | 'runs' | 'forecasts' | 'city' | 'governance';

const navigation: Array<{ key: NavKey; label: string; href: string }> = [
  { key: 'overview', label: '首页', href: '/' },
  { key: 'predict', label: '开始预测', href: '/predict' },
  { key: 'runs', label: '最近项目', href: '/runs' },
];

export function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span>Q</span><i />
    </span>
  );
}

export function AppShell({
  active,
  children,
}: {
  active: NavKey;
  title?: string;
  children: ReactNode;
}) {
  return (
    <main className="product-shell">
      <a className="skip-link" href="#main-content">跳到主要内容</a>
      <header className="product-header">
        <Link className="product-brand" href="/" aria-label="黔镜 QianScope 首页">
          <BrandMark />
          <span><strong>黔镜</strong><small>QIANSCOPE · SOCIAL WORLD</small></span>
        </Link>
        <nav aria-label="主要导航">
          {navigation.map((item) => (
            <Link
              aria-current={active === item.key ? 'page' : undefined}
              className={active === item.key ? 'active' : ''}
              href={item.href}
              key={item.key}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <Link className="header-start" href="/predict">开始预测 <span>↗</span></Link>
      </header>
      <div className="product-content" id="main-content">{children}</div>
      <footer className="product-footer">
        <span><strong>黔镜 QianScope</strong><br />开源的通用社会事件预测实验系统</span>
        <span>所有人群均为统计约束下的合成人格原型。<br />结果是条件概率模拟，不构成现实结果保证。</span>
      </footer>
    </main>
  );
}

export function PageIntro({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <section className="page-intro">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </section>
  );
}

export function DataModeBadge({ live }: { live: boolean }) {
  return <span className={live ? 'data-mode live' : 'data-mode'}>{live ? '已连接' : '示例数据'}</span>;
}
