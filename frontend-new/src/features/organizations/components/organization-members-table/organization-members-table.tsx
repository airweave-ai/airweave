import * as React from 'react';
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table';
import { IconDotsVertical, IconTrash } from '@tabler/icons-react';
import { isAssignableOrganizationMemberRole } from '../../lib/roles';
import { OrganizationMemberRoleControl } from './organization-member-role-control';
import { RemoveOrganizationMemberAlertDialog } from './remove-organization-member-alert-dialog';
import type { ColumnDef } from '@tanstack/react-table';
import type { MemberResponse } from '@/shared/api/generated';
import { UserAvatar } from '@/shared/components/user-avatar';
import { Button } from '@/shared/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/ui/table';
import { Badge } from '@/shared/ui/badge';

type OrganizationMembersTableProps = {
  canManageMembers: boolean;
  currentUserId: string;
  members: Array<MemberResponse>;
};

function OrganizationMembersTable({
  canManageMembers,
  currentUserId,
  members,
}: OrganizationMembersTableProps) {
  const [memberToRemove, setMemberToRemove] =
    React.useState<MemberResponse | null>(null);

  const columns = React.useMemo<Array<ColumnDef<MemberResponse>>>(
    () => [
      {
        id: 'member',
        header: 'Member',
        cell: ({ row }) => (
          <MemberCell
            member={row.original}
            isCurrentUser={row.original.id === currentUserId}
          />
        ),
      },
      {
        id: 'role',
        header: 'Role',
        cell: ({ row }) => {
          const member = row.original;

          return (
            <OrganizationMemberRoleControl
              canChangeRole={canManageMemberRow({
                canManageMembers,
                currentUserId,
                member,
              })}
              member={member}
            />
          );
        },
      },
      {
        id: 'actions',
        header: () => <span className="sr-only">Actions</span>,
        cell: ({ row }) => {
          const member = row.original;

          if (
            !canManageMemberRow({
              canManageMembers,
              currentUserId,
              member,
            })
          ) {
            return null;
          }

          return (
            <OrganizationMemberActionsMenu
              member={member}
              onRemove={setMemberToRemove}
            />
          );
        },
      },
    ],
    [canManageMembers, currentUserId],
  );

  const table = useReactTable({
    data: members,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id,
  });

  return (
    <>
      <Table className="table-fixed">
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id} className="hover:bg-transparent">
              {headerGroup.headers.map((header) => (
                <TableHead
                  key={header.id}
                  className={getHeaderCellClassName(header.column.id)}
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <TableRow key={row.id} className="h-14 hover:bg-transparent">
              {row.getVisibleCells().map((cell) => (
                <TableCell
                  key={cell.id}
                  className={getBodyCellClassName(cell.column.id)}
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <RemoveOrganizationMemberAlertDialog
        member={memberToRemove}
        onOpenChange={(open) => {
          if (!open) {
            setMemberToRemove(null);
          }
        }}
      />
    </>
  );
}

function MemberCell({
  member,
  isCurrentUser,
}: {
  member: MemberResponse;
  isCurrentUser: boolean;
}) {
  return (
    <div className="flex min-w-0 items-center gap-2">
      <UserAvatar name={member.name} email={member.email} />
      <div className="min-w-0">
        <div className="flex gap-2 truncate text-sm font-medium">
          {member.name}
          {isCurrentUser ? <Badge variant="secondary">You</Badge> : null}
        </div>
        <div className="truncate font-mono text-xs text-muted-foreground">
          {member.email}
        </div>
      </div>
    </div>
  );
}

function OrganizationMemberActionsMenu({
  member,
  onRemove,
}: {
  member: MemberResponse;
  onRemove: (member: MemberResponse) => void;
}) {
  return (
    <div className="flex justify-end">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            aria-label={`Open actions for ${member.name}`}
            size="icon"
            type="button"
            variant="ghost"
          >
            <IconDotsVertical />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-54">
          <DropdownMenuItem
            variant="destructive"
            onSelect={() => onRemove(member)}
          >
            <IconTrash />
            Remove from organization
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

function canManageMemberRow({
  canManageMembers,
  currentUserId,
  member,
}: {
  canManageMembers: boolean;
  currentUserId: string;
  member: MemberResponse;
}) {
  return (
    canManageMembers &&
    member.id !== currentUserId &&
    isAssignableOrganizationMemberRole(member.role)
  );
}

function getHeaderCellClassName(columnId: string) {
  const baseClassName = 'font-mono text-xs font-normal text-muted-foreground';

  if (columnId === 'role') {
    return `${baseClassName} w-55`;
  }

  if (columnId === 'member') {
    return `${baseClassName} w-85`;
  }

  return undefined;
}

function getBodyCellClassName(columnId: string) {
  if (columnId === 'actions') {
    return 'text-right';
  }

  return undefined;
}

export { OrganizationMembersTable };
