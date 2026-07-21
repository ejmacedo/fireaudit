import { isAxiosError } from "axios";

export function isUpgradeRequiredError(error: unknown): boolean {
  if (!isAxiosError(error)) return false;
  return (
    error.response?.status === 403 &&
    error.response?.data?.error?.code === "UPGRADE_REQUIRED"
  );
}
