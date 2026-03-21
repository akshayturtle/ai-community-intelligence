import { cn } from "../../lib/utils";

const variants: Record<string, string> = {
  emerging: "bg-bg-success text-txt-success",
  active: "bg-bg-info text-txt-info",
  peaking: "bg-[#FAECE7] text-[#993C1D]",
  declining: "bg-bg-secondary text-text-tertiary",
  positive: "bg-bg-success text-txt-success",
  negative: "bg-bg-danger text-txt-danger",
  neutral: "bg-bg-secondary text-text-secondary",
  critical: "bg-bg-danger text-txt-danger",
  high: "bg-bg-danger text-txt-danger",
  medium: "bg-bg-warning text-txt-warning",
  low: "bg-bg-secondary text-text-secondary",
  aligned: "bg-bg-success text-txt-success",
  overhyped: "bg-bg-danger text-txt-danger",
  underhyped: "bg-bg-info text-txt-info",
  flipped: "bg-bg-danger text-txt-danger",
  shifting: "bg-bg-warning text-txt-warning",
  "new voice": "bg-bg-success text-txt-success",
  "opinion leader": "bg-bg-purple text-txt-purple",
  default: "bg-bg-secondary text-text-secondary",
};

interface Props {
  label: string;
  variant?: string;
  className?: string;
}

export default function Badge({ label, variant, className }: Props) {
  const style = variants[variant || label.toLowerCase()] || variants.default;
  return (
    <span className={cn("inline-block px-2 py-0.5 rounded-md text-[11px] font-medium capitalize", style, className)}>
      {label}
    </span>
  );
}
