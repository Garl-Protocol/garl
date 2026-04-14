"use client";

import { useState } from "react";
import { Copy, Check, Share2 } from "lucide-react";

type Props = {
  receiptUrl: string;
  agentName: string;
  shortHash: string;
  verified: boolean;
};

export default function ReceiptActions({
  receiptUrl,
  agentName,
  shortHash,
  verified,
}: Props) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(receiptUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable */
    }
  }

  const tweetText = verified
    ? `✓ AI task cryptographically verified on @GARLProtocol\n${receiptUrl}`
    : `AI task receipt on @GARLProtocol\n${receiptUrl}`;
  const twitterHref = `https://twitter.com/intent/tweet?text=${encodeURIComponent(tweetText)}`;
  const linkedinHref = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(receiptUrl)}`;

  return (
    <div className="rounded-xl border border-garl-border bg-garl-surface p-4">
      <div className="mb-3 flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-garl-muted">
        <Share2 className="h-3 w-3" />
        Share Receipt
      </div>

      {/* URL + copy row */}
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-stretch">
        <code className="flex-1 overflow-x-auto whitespace-nowrap rounded-lg border border-garl-border bg-garl-bg px-3 py-2 font-mono text-[11px] text-garl-text">
          {receiptUrl}
        </code>
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-garl-border bg-garl-bg px-4 py-2 font-mono text-xs text-garl-text transition-colors hover:border-garl-accent/50 hover:text-garl-accent"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-garl-accent" />
              Copied
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              Copy
            </>
          )}
        </button>
      </div>

      {/* Social share */}
      <div className="flex flex-wrap gap-2">
        <a
          href={twitterHref}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-lg border border-garl-border bg-garl-bg px-3 py-2 font-mono text-xs text-garl-text transition-colors hover:border-garl-accent/50 hover:text-garl-accent"
          aria-label={`Share receipt for ${agentName} on Twitter/X`}
        >
          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" aria-hidden fill="currentColor">
            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
          </svg>
          Share on X
        </a>
        <a
          href={linkedinHref}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-lg border border-garl-border bg-garl-bg px-3 py-2 font-mono text-xs text-garl-text transition-colors hover:border-garl-accent/50 hover:text-garl-accent"
          aria-label={`Share receipt for ${agentName} on LinkedIn`}
        >
          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" aria-hidden fill="currentColor">
            <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.063 2.063 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
          </svg>
          LinkedIn
        </a>
        <span className="ml-auto self-center font-mono text-[10px] text-garl-muted/60">
          receipt <code className="text-garl-muted">{shortHash}</code>
        </span>
      </div>
    </div>
  );
}
