import Link from "next/link";
import PrivacyPreference from "./PrivacyPreference";

export default function PrivacyPage() {
  return <main className="container max-w-3xl py-10">
    <Link href="/" className="inline-flex min-h-12 items-center underline underline-offset-4">Back to STYL</Link>
    <h1 className="mt-5 text-3xl font-semibold">Privacy</h1>
    <section className="mt-6 space-y-3 leading-7" aria-labelledby="measurement-title">
      <h2 id="measurement-title" className="text-xl font-semibold">Website usage measurement</h2>
      <p>STYL uses first-party, aggregate-only measurement to understand page views, equipment interest, cart and quote actions, estimated active time and site performance. You do not need to dismiss a banner or agree to tracking to browse the store.</p>
      <p>Measurement does not create analytics cookies, browser or session identifiers, individual browsing histories, or cross-visit profiles. The collector does not store raw IP addresses, full URLs, search parameters, or form contents. Page names are reduced to predefined categories.</p>
      <p>Requests are combined into hourly totals and separate coarse breakdowns, such as country, currency, traffic source and device category. Country is estimated by the server; it is not a precise location. Aggregate totals have no automatic age expiry; administrators can archive them and explicitly remove backed-up records from the server. Private backup copies may be retained separately. Totals cannot be used to retrieve or delete an individual visitor&apos;s activity.</p>
      <p>Do Not Track and Global Privacy Control signals are respected. You can also turn off optional usage measurement for this browser below. This saves only an on/off preference, not an identifier. Clearing site storage resets that preference.</p>
      <PrivacyPreference />
    </section>
    <section className="mt-8 space-y-3 leading-7" aria-labelledby="support-privacy-title">
      <h2 id="support-privacy-title" className="text-xl font-semibold">Ask STYL local testing</h2>
      <p>The chat feature is currently a local testing prototype, not a production support service. Use only synthetic, non-sensitive test messages. Do not enter real contact information, addresses, credentials or private documents. Gemini&apos;s unpaid API may use submitted content and responses for product improvement or human review.</p>
      <p>Chat messages and human replies are stored separately from traffic analytics. A private access token saved in your browser lets you resume your guest conversation on that browser. Other browser profiles get separate conversations; clearing browser storage loses this access. Do not use guest chat on a shared device for private information.</p>
      <p>The support inbox lets the authorized operator read conversations, take over and reply. AI receives only a bounded conversation context and allowlisted published catalog facts. Chat history has no automatic age expiry, is included in private backups, and can be explicitly removed when a closed conversation has been backed up and the download verified. Privacy deletion requests remain separate.</p>
    </section>
    <section className="mt-8 space-y-3 leading-7" aria-labelledby="inquiry-privacy-title">
      <h2 id="inquiry-privacy-title" className="text-xl font-semibold">Inquiries and essential site functions</h2>
      <p>If you submit an inquiry, STYL receives the contact information and message you choose to provide so we can respond. This business information is separate from usage measurement and is not linked to an analytics visitor profile. Do not include sensitive information in your inquiry.</p>
      <p>Your cart is stored in your browser so it remains available while you shop. Admin authentication uses separate browser storage. Hosting and security systems may process IP addresses and access logs to deliver and protect the website; these are separate from the aggregate analytics store.</p>
      <p>Website logs and business inquiries are not automatically deleted because of their age. Access is restricted, and administrators can download private backups and explicitly remove backed-up server records. This does not override applicable privacy obligations or requests to delete personal information, including relevant backup copies.</p>
      <p>For privacy questions or requests about information you have submitted, contact <a href="mailto:styl@stylfitness.com" className="underline underline-offset-4">styl@stylfitness.com</a>.</p>
    </section>
  </main>;
}
