import { Lightbulb } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AuthProviderTable } from "@/components/auth-providers/AuthProviderTable";

const AuthProviders = () => {
    return (
        <div className="mx-auto w-full max-w-[1800px] px-6 py-6 pb-8">
            <div className="space-y-6 md:space-y-8">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl sm:text-3xl font-bold">Auth Providers</h1>
                        <p className="text-xs sm:text-sm text-muted-foreground mt-1 sm:mt-2">
                            Authenticate data sources through third-party applications.
                        </p>
                    </div>
                    <div className="flex space-x-2">
                        <Button
                            variant="outline"
                            onClick={() => window.open("https://docs.airweave.ai/auth-providers", "_blank")}
                        >
                            <Lightbulb className="h-4 w-4" />
                            Learn More
                        </Button>
                    </div>
                </div>

                <AuthProviderTable />
            </div>
        </div>
    );
};

export default AuthProviders;
