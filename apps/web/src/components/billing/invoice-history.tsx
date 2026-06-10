"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { useInvoices } from "@/hooks/use-billing";
import { formatPrice, formatDate } from "@/lib/format";
import { ExternalLink, Download, Inbox } from "lucide-react";

const PAGE_SIZE = 10;

function invoiceStatusBadge(status: string) {
  switch (status) {
    case "paid":
      return (
        <Badge variant="default" className="bg-green-600 hover:bg-green-600/80">
          Paid
        </Badge>
      );
    case "open":
      return (
        <Badge variant="default" className="bg-blue-600 hover:bg-blue-600/80">
          Open
        </Badge>
      );
    case "uncollectible":
      return <Badge variant="destructive">Uncollectible</Badge>;
    case "void":
      return <Badge variant="secondary">Void</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

export function InvoiceHistory() {
  const [skip, setSkip] = useState(0);
  const { data, isLoading } = useInvoices({ skip, limit: PAGE_SIZE });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-36" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  const invoices = data?.items ?? [];
  const total = data?.total ?? 0;
  const hasMore = skip + PAGE_SIZE < total;
  const hasPrev = skip > 0;

  if (invoices.length === 0 && skip === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Invoice History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Inbox className="mb-3 h-10 w-10 text-muted-foreground/50" />
            <p className="text-sm font-medium text-muted-foreground">
              No invoices yet
            </p>
            <p className="mt-1 text-xs text-muted-foreground/70">
              Invoices will appear here after your first payment
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Invoice History</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {invoices.map((invoice) => (
              <TableRow key={invoice.id}>
                <TableCell className="font-medium">
                  {formatDate(invoice.created_at)}
                </TableCell>
                <TableCell>
                  {formatPrice(invoice.amount_cents, invoice.currency)}
                </TableCell>
                <TableCell>{invoiceStatusBadge(invoice.status)}</TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-2">
                    {invoice.hosted_invoice_url && (
                      <Button
                        variant="ghost"
                        size="sm"
                        asChild
                      >
                        <a
                          href={invoice.hosted_invoice_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      </Button>
                    )}
                    {invoice.invoice_pdf_url && (
                      <Button
                        variant="ghost"
                        size="sm"
                        asChild
                      >
                        <a
                          href={invoice.invoice_pdf_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <Download className="h-4 w-4" />
                        </a>
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        <div className="mt-4 flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            Showing {skip + 1}–{Math.min(skip + PAGE_SIZE, total)} of {total}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
              disabled={!hasPrev}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSkip(skip + PAGE_SIZE)}
              disabled={!hasMore}
            >
              Next
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
