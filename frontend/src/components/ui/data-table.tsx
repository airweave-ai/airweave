import { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface Column<T> {
  header: string;
  accessorKey?: keyof T;
  cell?: (item: T) => React.ReactNode;
  className?: string;
}

export interface PaginationState {
  pageIndex: number;
  pageSize: number;
}

export interface PaginationInfo {
  pageCount: number;
  totalItems: number;
}

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  pagination?: PaginationState;
  paginationInfo?: PaginationInfo;
  isLoading?: boolean;
  searchPlaceholder?: string;
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  onRowClick?: (item: T) => void;
  onPaginationChange?: (pagination: PaginationState) => void;
  emptyMessage?: string;
  loadingMessage?: string;
}

export function DataTable<T extends Record<string, any>>({
  data,
  columns,
  pagination = { pageIndex: 0, pageSize: 10 },
  paginationInfo = { pageCount: 1, totalItems: 0 },
  isLoading = false,
  searchPlaceholder = "Search...",
  searchValue = "",
  onSearchChange,
  onRowClick,
  onPaginationChange,
  emptyMessage = "No data found",
  loadingMessage = "Loading...",
}: DataTableProps<T>) {
  const showPagination = !!onPaginationChange && paginationInfo.pageCount > 1;

  const handlePreviousPage = () => {
    if (pagination.pageIndex > 0 && onPaginationChange) {
      onPaginationChange({
        ...pagination,
        pageIndex: pagination.pageIndex - 1,
      });
    }
  };

  const handleNextPage = () => {
    if (pagination.pageIndex < paginationInfo.pageCount - 1 && onPaginationChange) {
      onPaginationChange({
        ...pagination,
        pageIndex: pagination.pageIndex + 1,
      });
    }
  };

  return (
    <div className="bg-background rounded-lg border">
      {onSearchChange && (
        <div className="p-4 border-b">
          <div className="relative">
            <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder={searchPlaceholder}
              value={searchValue}
              onChange={(e) => onSearchChange(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>
      )}

      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            {columns.map((column, index) => (
              <TableHead
                key={index}
                className={cn("font-semibold text-foreground", column.className)}
              >
                {column.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow>
              <TableCell colSpan={columns.length} className="text-center py-16">
                <div className="flex items-center justify-center text-muted-foreground">
                  {loadingMessage}
                </div>
              </TableCell>
            </TableRow>
          ) : data.length === 0 ? (
            <TableRow>
              <TableCell colSpan={columns.length} className="text-center py-16">
                <div className="flex flex-col items-center justify-center text-muted-foreground">
                  <p>{emptyMessage}</p>
                  {onSearchChange && searchValue && (
                    <p className="text-sm mt-1">Try adjusting your search terms</p>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ) : (
            data.map((item, rowIndex) => (
              <TableRow
                key={rowIndex}
                className={cn(
                  onRowClick && "cursor-pointer hover:bg-muted/50 transition-colors"
                )}
                onClick={() => onRowClick?.(item)}
              >
                {columns.map((column, colIndex) => (
                  <TableCell key={colIndex} className={column.className}>
                    {column.cell
                      ? column.cell(item)
                      : column.accessorKey
                      ? String(item[column.accessorKey] ?? "-")
                      : null}
                  </TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {showPagination && (
        <div className="flex items-center justify-between p-4 border-t">
          <div className="text-sm text-muted-foreground">
            Showing {pagination.pageIndex * pagination.pageSize + 1}-
            {Math.min((pagination.pageIndex + 1) * pagination.pageSize, paginationInfo.totalItems)} of{" "}
            {paginationInfo.totalItems} items
          </div>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePreviousPage}
              disabled={pagination.pageIndex === 0}
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Previous
            </Button>
            <div className="text-sm whitespace-nowrap">
              Page {pagination.pageIndex + 1} of {paginationInfo.pageCount}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleNextPage}
              disabled={pagination.pageIndex >= paginationInfo.pageCount - 1}
            >
              Next
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
