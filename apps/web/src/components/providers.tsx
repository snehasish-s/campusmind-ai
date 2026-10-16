"use client";
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "motion/react";
import { Toaster } from "sonner";
export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 1, staleTime: 15000, refetchOnWindowFocus: false },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <MotionConfig reducedMotion="user">
        {children}
        <Toaster position="bottom-right" richColors closeButton />
      </MotionConfig>
    </QueryClientProvider>
  );
}
