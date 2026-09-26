"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import BrandLogo from "./BrandLogo";

const links = [
  { href: "/#products", label: "Products" },
  { href: "/accessories", label: "Accessories" },
  { href: "/#about", label: "About" },
  { href: "/#contact", label: "Request a quote" },
];

export default function StoreHeader({ cartCount }: { cartCount: number }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const closeOnDesktop = () => {
      if (window.innerWidth >= 1024) dialog.current?.close();
    };
    window.addEventListener("resize", closeOnDesktop);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("resize", closeOnDesktop);
    };
  }, [open]);
  return (
    <header className="sticky top-0 z-40 border-b border-[var(--line)] bg-white/95 backdrop-blur-md">
      <div className="container flex min-h-16 flex-wrap items-center justify-between gap-2 py-2 lg:min-h-20">
        <Link href="/" className="inline-flex min-h-11 items-center" aria-label="STYL home"><BrandLogo markClassName="h-8 w-auto" /></Link>
        <nav aria-label="Main navigation" className="hidden items-center gap-6 text-sm lg:flex">
          {links.map((link) => <Link key={link.href} href={link.href} className="inline-flex min-h-11 items-center hover:underline">{link.label}</Link>)}
        </nav>
        <div className="flex items-center gap-2">
          <Link href="/cart" className="inline-flex min-h-11 items-center rounded-full border border-[var(--line)] px-3 text-sm font-medium">Cart ({cartCount})</Link>
          <button ref={trigger} type="button" className="min-h-11 rounded-full border border-[var(--line)] px-3 text-sm lg:hidden" aria-haspopup="dialog" aria-expanded={open} onClick={() => { dialog.current?.showModal(); setOpen(true); }}>Menu</button>
        </div>
      </div>
      <dialog ref={dialog} aria-label="Site navigation" className="fixed inset-0 m-auto w-[calc(100%-32px)] max-w-md rounded-2xl bg-white p-5 text-[var(--ink)] backdrop:bg-black/60" onClick={(event) => { if (event.target === event.currentTarget) dialog.current?.close(); }} onClose={() => { setOpen(false); trigger.current?.focus(); }}>
        <div className="flex items-center justify-between"><h2 className="text-xl font-semibold">Explore STYL</h2><button type="button" onClick={() => dialog.current?.close()} className="min-h-11 px-3">Close</button></div>
        <nav aria-label="Mobile navigation" className="mt-4 grid gap-2">
          {links.map((link) => <Link key={link.href} href={link.href} className="rounded-lg px-3 py-4 hover:bg-neutral-100" onClick={() => dialog.current?.close()}>{link.label}</Link>)}
        </nav>
      </dialog>
    </header>
  );
}
