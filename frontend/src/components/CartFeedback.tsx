import Link from "next/link";

export default function CartFeedback({ error, notice }: { error: string | null; notice: string | null }) {
  return (
    <>
      {error ? <p role="alert" className="my-3 min-w-0 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800 [overflow-wrap:anywhere]">{error}</p> : null}
      <div role="status" aria-live="polite" className={notice ? "my-3 min-w-0 rounded-lg bg-green-50 p-3 text-sm text-green-900 [overflow-wrap:anywhere]" : ""}>
        {notice ? <>{notice} <Link href="/cart" className="inline-flex min-h-11 items-center underline">View cart</Link></> : null}
      </div>
    </>
  );
}
