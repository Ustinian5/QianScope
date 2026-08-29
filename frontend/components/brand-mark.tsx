import Image from 'next/image';

export function QianScopeMark({ className }: { className?: string }) {
  return (
    <Image
      alt=""
      aria-hidden="true"
      className={className}
      draggable={false}
      height={454}
      src="/gravity-echo-mark-ink.png"
      width={732}
    />
  );
}
