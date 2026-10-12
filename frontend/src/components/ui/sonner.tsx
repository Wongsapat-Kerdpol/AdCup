"use client";

import { Toaster as Sonner, type ToasterProps } from "sonner";

// Usage anywhere:  import { toast } from "sonner";  toast.success("Campaign created");
function Toaster(props: ToasterProps) {
  return (
    <Sonner
      theme="light"
      position="bottom-right"
      richColors
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
        } as React.CSSProperties
      }
      {...props}
    />
  );
}

export { Toaster };
