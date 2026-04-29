import { OrganizationIcon } from './organization-icon';
import { OrganizationRoleBadge } from './organization-role-badge';
import type { OrganizationWithRole } from '@/shared/api';
import { formatDate } from '@/shared/format/date';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/ui/table';

type OrganizationsCardProps = {
  organizations: Array<OrganizationWithRole>;
};

function OrganizationsCard({ organizations }: OrganizationsCardProps) {
  return (
    <Card className="gap-0 rounded-lg bg-foreground/5 py-0 shadow-xs">
      <CardHeader className="gap-1.5 px-4 pt-4 pb-0">
        <CardTitle className="text-xl leading-7 font-semibold">
          Organizations
        </CardTitle>
        <CardDescription>
          You are the member of organizations listed below
        </CardDescription>
      </CardHeader>

      <CardContent className="p-4">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Organization name</TableHead>
              <TableHead>Joined</TableHead>
              <TableHead className="text-right">Role</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {organizations.map((organization) => (
              <TableRow key={organization.id} className="hover:bg-transparent">
                <TableCell>
                  <div className="flex min-w-0 items-center gap-2 font-medium">
                    <OrganizationIcon name={organization.name} />
                    <span className="truncate">{organization.name}</span>
                  </div>
                </TableCell>
                <TableCell className="font-mono text-muted-foreground">
                  {formatDate(organization.created_at) ?? organization.created_at}
                </TableCell>
                <TableCell className="text-right">
                  <OrganizationRoleBadge role={organization.role} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

export { OrganizationsCard };
