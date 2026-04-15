import { ProviderSettingsManager } from "@/components/provider-settings-manager";
import { OrganizationSettings } from "@/components/organization-settings";

export default function SettingsPage() {
    return (
        <div className="space-y-6">
            <OrganizationSettings />
            <ProviderSettingsManager />
        </div>
    );
}
