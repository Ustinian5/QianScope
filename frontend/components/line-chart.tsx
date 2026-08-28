'use client';

import { useEffect, useRef } from 'react';

export type ChartSeries = {
  label: string;
  color: string;
  values: Array<{ x: number; y: number }>;
};

function renderChart(
  canvas: HTMLCanvasElement,
  series: ChartSeries[],
  yDomain: [number, number],
  formatY: (value: number) => string,
) {
  const rect = canvas.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return;
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(rect.width * ratio);
  canvas.height = Math.round(rect.height * ratio);
  const context = canvas.getContext('2d');
  if (!context) return;
  context.scale(ratio, ratio);

  const width = rect.width;
  const height = rect.height;
  const padding = { top: 18, right: 16, bottom: 30, left: 45 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const allX = series.flatMap((item) => item.values.map((point) => point.x));
  const minX = Math.min(...allX, 0);
  const maxX = Math.max(...allX, 1);
  const [minY, maxY] = yDomain;
  const mapX = (value: number) => padding.left + ((value - minX) / Math.max(1, maxX - minX)) * plotWidth;
  const mapY = (value: number) => padding.top + (1 - (value - minY) / Math.max(0.0001, maxY - minY)) * plotHeight;

  context.clearRect(0, 0, width, height);
  context.font = '11px ui-sans-serif, -apple-system, BlinkMacSystemFont, sans-serif';
  context.textBaseline = 'middle';

  for (let index = 0; index <= 4; index += 1) {
    const value = minY + ((maxY - minY) * index) / 4;
    const y = mapY(value);
    context.strokeStyle = 'rgba(26, 31, 36, .09)';
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(padding.left, y);
    context.lineTo(width - padding.right, y);
    context.stroke();
    context.fillStyle = '#77736d';
    context.textAlign = 'right';
    context.fillText(formatY(value), padding.left - 9, y);
  }

  const tickCount = Math.min(5, Math.max(2, Math.floor(plotWidth / 110)));
  for (let index = 0; index <= tickCount; index += 1) {
    const value = minX + ((maxX - minX) * index) / tickCount;
    context.fillStyle = '#77736d';
    context.textAlign = index === 0 ? 'left' : index === tickCount ? 'right' : 'center';
    context.fillText(`第 ${Math.round(value)} 步`, mapX(value), height - 11);
  }

  series.forEach((item) => {
    if (item.values.length === 0) return;
    context.strokeStyle = item.color;
    context.lineWidth = 2;
    context.lineJoin = 'round';
    context.lineCap = 'round';
    context.beginPath();
    item.values.forEach((point, index) => {
      const x = mapX(point.x);
      const y = mapY(point.y);
      if (index === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    });
    context.stroke();

    const finalPoint = item.values[item.values.length - 1];
    context.fillStyle = item.color;
    context.beginPath();
    context.arc(mapX(finalPoint.x), mapY(finalPoint.y), 3.3, 0, Math.PI * 2);
    context.fill();
  });
}

export function LineChart({
  series,
  yDomain = [0, 1],
  formatY = (value) => `${Math.round(value * 100)}%`,
  label,
}: {
  series: ChartSeries[];
  yDomain?: [number, number];
  formatY?: (value: number) => string;
  label: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const redraw = () => renderChart(canvas, series, yDomain, formatY);
    const observer = new ResizeObserver(redraw);
    observer.observe(canvas);
    redraw();
    return () => observer.disconnect();
  }, [series, yDomain, formatY]);

  return (
    <div className="line-chart" role="img" aria-label={label}>
      <canvas ref={canvasRef} aria-hidden="true" />
      <table className="sr-only">
        <caption>{label}</caption>
        <thead><tr><th>序列</th><th>数据点</th></tr></thead>
        <tbody>
          {series.map((item) => (
            <tr key={item.label}>
              <th>{item.label}</th>
              <td>{item.values.map((point) => `${point.x}: ${formatY(point.y)}`).join(', ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
