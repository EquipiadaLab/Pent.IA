import { Card, CardHeader, CardTitle } from "./ui/card";

import { DashboardHeader } from "./dashboard.header";

export default function Campanha() {
    return (
        <div>
            <DashboardHeader
                title="Campanha em execução"
                description="O agente está valida a superfície autorizada, lance a lance."
            />
            <Card className="mt-4 w-full">
                <CardHeader>
                    <CardTitle></CardTitle>
                </CardHeader>
            </Card>
        </div>
    );
}