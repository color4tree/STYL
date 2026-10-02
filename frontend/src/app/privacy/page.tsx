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
      <h2 id="support-privacy-title" className="text-xl font-semibold">STYL Assistant and team follow-up</h2>
      <p>STYL Assistant uses AI and is currently being tested locally, not offered as a production support service. Chat messages and selected STYL catalog context may be sent to OpenAI. OpenAI API inputs and outputs are not used to train its models by default. STYL requests use <code>store: false</code> to disable response storage, but this does not guarantee zero retention: provider abuse-monitoring logs and applicable retention policies may still apply. Use synthetic, non-sensitive questions for local testing; do not put confidential information, payment details, credentials or private documents in chat messages.</p>
      <p>Authorized administrators can add product manuals through Customer support → Knowledge. Only approved public, non-sensitive documents and media may be sent for extraction: images and PDFs to OpenAI, and videos only to Google Gemini. Gemini is not used for customer chat. Google&apos;s unpaid video-processing services may use submitted content for product improvement and human review. STYL stores uploads privately and retrieves facts for chat only after an administrator assigns products, reviews the extracted draft and approves it. Paid API usage may apply; STYL does not automatically upgrade a plan or enable billing.</p>
      <p>You do not need an account or contact details to chat. When a question needs a team reply, you may optionally share your name and email in the dedicated contact fields so STYL can follow up. These contact details are stored separately from chat messages, are private to the authorized STYL team and your guest conversation, and are never sent to the AI model or usage analytics. You can edit them using the contact-details action in your conversation. During local testing, use synthetic contact details.</p>
      <p>Chat messages and human replies are stored separately from traffic analytics. A private access token saved in your browser lets you resume your guest conversation on that browser. Other browser profiles get separate conversations; clearing browser storage loses this access. Do not use guest chat on a shared device for private information.</p>
      <p>The support inbox lets the authorized operator read conversations and contact details, and reply to individual questions while the assistant keeps helping. Saving a request or contact details does not mean a team member is online, guarantee a response time, or send an email automatically. AI receives only a bounded conversation context and approved catalog information, not the dedicated contact fields. Chat history and contact details have no automatic age expiry, are included in private backups, and can be explicitly removed when a closed conversation has been backed up and the download verified. Privacy deletion requests remain separate.</p>
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
