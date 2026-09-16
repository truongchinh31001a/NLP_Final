"use client";

import { ConfigProvider } from "antd";
import type { ReactNode } from "react";

import { designTokens } from "@/lib/design-tokens";

type ProvidersProps = {
  children: ReactNode;
};

export function Providers({ children }: ProvidersProps) {
  return (
    <ConfigProvider
      theme={{
        token: {
          colorBgBase: designTokens.color.bgPage,
          colorBgContainer: designTokens.color.bgSurface,
          colorBorder: designTokens.color.borderSubtle,
          colorErrorBg: designTokens.color.statusErrorSoft,
          colorInfoBg: designTokens.color.statusInfoSoft,
          colorPrimary: designTokens.color.actionPrimaryFill,
          colorPrimaryBg: designTokens.color.actionPrimarySoft,
          colorSuccess: designTokens.color.statusSuccess,
          colorText: designTokens.color.textStrong,
          colorTextSecondary: designTokens.color.textMuted,
          colorWarningBg: designTokens.color.statusWarningSoft,
          borderRadius: designTokens.radius.control,
          fontFamily: "var(--font-sans), sans-serif",
        },
      }}
    >
      {children}
    </ConfigProvider>
  );
}
