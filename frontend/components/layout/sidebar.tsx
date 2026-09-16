"use client";

import {
  BarChartOutlined,
  BookOutlined,
  CalendarOutlined,
  HomeOutlined,
  MessageOutlined,
  ReadOutlined,
  UserOutlined,
} from "@ant-design/icons";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

type NavItem = {
  href: string;
  label: string;
  icon: ReactNode;
  match: (pathname: string) => boolean;
};

const navItems: NavItem[] = [
  {
    href: "/home",
    label: "Home",
    icon: <HomeOutlined />,
    match: (pathname) => pathname === "/home",
  },
  {
    href: "/tutor",
    label: "AI Tutor",
    icon: <MessageOutlined />,
    match: (pathname) => pathname.startsWith("/tutor"),
  },
  {
    href: "/practice/demo-activity",
    label: "Practice",
    icon: <ReadOutlined />,
    match: (pathname) => pathname.startsWith("/practice"),
  },
  {
    href: "/learn",
    label: "Learn",
    icon: <BookOutlined />,
    match: (pathname) => pathname.startsWith("/learn"),
  },
  {
    href: "/progress",
    label: "Progress",
    icon: <BarChartOutlined />,
    match: (pathname) => pathname.startsWith("/progress"),
  },
  {
    href: "/plan",
    label: "Plan",
    icon: <CalendarOutlined />,
    match: (pathname) => pathname.startsWith("/plan"),
  },
  {
    href: "/profile",
    label: "Profile",
    icon: <UserOutlined />,
    match: (pathname) => pathname.startsWith("/profile"),
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <>
      <aside className="sticky top-0 hidden h-screen w-[248px] shrink-0 bg-ae-sidebar px-ae-lg py-ae-xl text-white md:flex md:flex-col">
        <Link href="/home" className="flex items-center gap-ae-sm text-white">
          <span className="grid size-10 place-items-center rounded-ae-compact bg-white text-ae-primary">
            LF
          </span>
          <span className="min-w-0">
            <span className="block text-[11px] font-semibold uppercase text-white/55">
              Adaptive English
            </span>
            <strong className="block truncate text-[18px] leading-tight">
              LingoFlow
            </strong>
          </span>
        </Link>

        <nav className="mt-ae-2xl flex flex-1 flex-col gap-ae-xs" aria-label="Main">
          {navItems.map((item) => {
            const active = item.match(pathname);
            return (
              <Link
                aria-current={active ? "page" : undefined}
                className={`flex h-11 items-center gap-ae-sm rounded-ae-control px-ae-sm text-[14px] font-semibold transition ${
                  active
                    ? "bg-white text-ae-primary"
                    : "text-white/70 hover:bg-white/10 hover:text-white"
                }`}
                href={item.href}
                key={item.href}
              >
                <span className="grid size-5 place-items-center text-[17px]">
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="rounded-ae-card border border-white/10 bg-white/8 p-ae-card">
          <p className="mb-ae-xs text-[11px] font-semibold uppercase text-white/55">
            Today
          </p>
          <p className="mb-0 text-[13px] leading-5 text-white/82">
            Keep one short loop: explain, practice, review, then update the plan.
          </p>
        </div>
      </aside>

      <nav
        className="fixed inset-x-0 bottom-0 z-50 grid h-16 grid-cols-7 border-t border-ae-line bg-ae-surface/95 px-ae-xs shadow-[0_-10px_30px_rgba(15,23,42,0.08)] backdrop-blur md:hidden"
        aria-label="Main"
      >
        {navItems.map((item) => {
          const active = item.match(pathname);
          return (
            <Link
              aria-current={active ? "page" : undefined}
              className={`flex min-w-0 flex-col items-center justify-center gap-1 text-[10px] font-semibold ${
                active ? "text-ae-primary" : "text-ae-muted"
              }`}
              href={item.href}
              key={item.href}
            >
              <span className="text-[18px]">{item.icon}</span>
              <span className="max-w-full truncate">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
