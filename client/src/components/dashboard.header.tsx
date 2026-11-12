interface DashboardHeaderProps {
    title?: string;
    description?: string;
    actions?: React.ReactNode;
}

export function DashboardHeader({ title, description, actions }: DashboardHeaderProps) {
    return (
        <div className="flex items-end justify-between pt-8">
            <div>
                <h1 className="text-4xl font-semibold">{title}</h1>
                {description && (
                    <p className="text-muted-foreground">
                        {description}
                    </p>
                )}
            </div>
            {actions && (
                <div className="ml-auto flex items-center space-x-2">
                    {actions}
                </div>
            )}
        </div>
    );
}