export function statusDotColor(status: string): string {
  if (status === "active") return "bg-green-500";
  if (status === "offline") return "bg-red-500";
  return "bg-gray-400";
}

export function statusLabel(status: string): string {
  if (status === "active") return "Online";
  if (status === "offline") return "Offline";
  return status;
}

export function formatLastSeen(lastSeenAt: string | null): string {
  if (!lastSeenAt) return "Never";
  const diffMs = Date.now() - new Date(lastSeenAt).getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
}
