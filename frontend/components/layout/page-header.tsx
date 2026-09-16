import type { ReactNode } from "react";

type PageHeaderProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
};

export function PageHeader({
  actions,
  description,
  eyebrow,
  title,
}: PageHeaderProps) {
  return (
    <header className="mb-ae-section flex flex-col gap-ae-md md:flex-row md:items-start md:justify-between">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="mb-ae-xs text-[11px] font-bold uppercase tracking-[0.08em] text-ae-primary">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="mb-ae-xs text-[28px] font-bold leading-tight tracking-normal md:text-[34px]">
          {title}
        </h1>
        {description ? (
          <p className="mb-0 max-w-3xl text-[15px] leading-6 text-ae-muted">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div className="shrink-0">{actions}</div> : null}
    </header>
  );
}
