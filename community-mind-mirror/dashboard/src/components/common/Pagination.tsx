import { ChevronLeft, ChevronRight } from "lucide-react";

interface Props {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onChange?: (page: number) => void;
}

export default function Pagination({ page, totalPages, onPageChange, onChange }: Props) {
  if (totalPages <= 1) return null;
  const handler = onChange || onPageChange;

  return (
    <div className="flex items-center gap-2 justify-center mt-4">
      <button
        onClick={() => handler(page - 1)}
        disabled={page <= 1}
        className="p-1.5 rounded-lg border border-border-primary text-text-secondary hover:text-text-primary hover:bg-bg-secondary disabled:opacity-30 disabled:cursor-not-allowed"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>
      <span className="text-sm text-text-secondary">
        Page {page} of {totalPages}
      </span>
      <button
        onClick={() => handler(page + 1)}
        disabled={page >= totalPages}
        className="p-1.5 rounded-lg border border-border-primary text-text-secondary hover:text-text-primary hover:bg-bg-secondary disabled:opacity-30 disabled:cursor-not-allowed"
      >
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}
