import React from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { useSidePanelStore } from "@/lib/stores/sidePanelStore";
import { SourceListView } from './views/panel/SourceListView';
import { CollectionFormView } from './views/panel/CollectionFormView';
import { SourceConfigView } from './views/panel/SourceConfigView';
import { OAuthRedirectView } from './views/panel/OAuthRedirectView';

const viewMap = {
    sourceList: SourceListView,
    collectionForm: CollectionFormView,
    sourceConfig: SourceConfigView,
    oauthRedirect: OAuthRedirectView,
};

const titleMap = {
    sourceList: 'Add a source',
    collectionForm: 'Create a new collection',
    sourceConfig: 'Connect source',
    oauthRedirect: 'Continue to authenticate',
};

const descriptionMap = {
    sourceList: 'Select a source to connect to your collection.',
    collectionForm: 'Give your new collection a name to get started.',
    sourceConfig: 'Provide credentials to connect your source.',
    oauthRedirect: 'You will be redirected to complete the connection.',
};


export const SidePanelFlow = () => {
    const { isOpen, closePanel, currentView, context } = useSidePanelStore();

    const CurrentViewComponent = currentView ? viewMap[currentView] : null;

    const handleOpenChange = (open: boolean) => {
        if (!open) {
            closePanel();
        }
    };

    return (
        <Sheet open={isOpen} onOpenChange={handleOpenChange}>
            <SheetContent className="w-[450px] sm:w-[540px] flex flex-col p-0">
                <SheetHeader className="p-6 pb-4">
                    <SheetTitle className="text-2xl">
                        {currentView ? titleMap[currentView] : 'Connect'}
                    </SheetTitle>
                    <SheetDescription>
                        {currentView ? descriptionMap[currentView] : 'Follow the steps to connect your data.'}
                    </SheetDescription>
                </SheetHeader>
                <div className="flex-grow overflow-y-auto">
                    {CurrentViewComponent && <CurrentViewComponent context={context} />}
                </div>
            </SheetContent>
        </Sheet>
    );
};
