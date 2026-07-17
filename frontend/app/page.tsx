import { HomeClient } from "@/components/HomeClient";
import { OpportunityPreview } from "@/components/design/OpportunityPreview";
import { Shell } from "@/components/Shell";

export default function Page() {
  return (
    <Shell>
      {process.env.NEXT_PUBLIC_DESIGN_PREVIEW === "1" ? <OpportunityPreview /> : <HomeClient />}
    </Shell>
  );
}
