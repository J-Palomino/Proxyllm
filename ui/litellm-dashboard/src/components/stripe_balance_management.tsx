import React, { useState, useEffect } from "react";
import {
  Card,
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  TableCell,
  TableBody,
  Text,
  Grid,
  Button,
  TextInput,
  Badge,
  Flex,
  Title,
} from "@tremor/react";

import {
  SearchIcon,
  RefreshIcon,
} from "@heroicons/react/outline";

import {
  message,
  Spin,
  Alert,
  Tooltip,
  Tag,
} from "antd";

import { parseErrorMessage } from "./shared/errorUtils";

interface StripeBalanceManagementProps {
  accessToken: string | null;
  userRole: string | null;
  userID: string | null;
  premiumUser: boolean;
}

interface BalanceRecord {
  id: string;
  customer_id: string;
  customer_type: string;
  stripe_customer_id: string;
  balance: number;
  total_topups: number;
  total_spent: number;
  low_balance_threshold: number | null;
  created_at: string;
  updated_at: string;
}

const StripeBalanceManagement: React.FC<StripeBalanceManagementProps> = ({
  accessToken,
  userRole,
  userID,
  premiumUser,
}) => {
  // State management
  const [balances, setBalances] = useState<BalanceRecord[]>([]);
  const [filteredBalances, setFilteredBalances] = useState<BalanceRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");

  // Fetch all balances
  const fetchBalances = async () => {
    if (!accessToken) {
      message.error("No access token available");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch("/stripe/balances/all", {
        method: "GET",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to fetch balances");
      }

      const data = await response.json();
      setBalances(data.balances || []);
      setFilteredBalances(data.balances || []);
      message.success("Balances loaded successfully");
    } catch (error: any) {
      const errorMessage = parseErrorMessage(error);
      message.error(`Failed to fetch balances: ${errorMessage}`);
      console.error("Error fetching balances:", error);
    } finally {
      setLoading(false);
    }
  };

  // Search/filter balances
  useEffect(() => {
    if (!searchTerm) {
      setFilteredBalances(balances);
      return;
    }

    const filtered = balances.filter(
      (b) =>
        b.customer_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        b.customer_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
        b.stripe_customer_id.toLowerCase().includes(searchTerm.toLowerCase())
    );
    setFilteredBalances(filtered);
  }, [searchTerm, balances]);

  // Load balances on mount
  useEffect(() => {
    fetchBalances();
  }, [accessToken]);

  // Format currency
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  };

  // Format date
  const formatDate = (dateString: string) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleString();
  };

  // Get balance badge color
  const getBalanceBadge = (balance: number, threshold: number | null) => {
    if (balance <= 0) return <Badge color="red">Empty</Badge>;
    if (threshold && balance < threshold) return <Badge color="yellow">Low</Badge>;
    if (balance < 10) return <Badge color="orange">Low</Badge>;
    return <Badge color="green">Active</Badge>;
  };

  // Calculate statistics
  const stats = {
    totalUsers: balances.length,
    totalBalance: balances.reduce((sum, b) => sum + b.balance, 0),
    totalTopups: balances.reduce((sum, b) => sum + b.total_topups, 0),
    totalSpent: balances.reduce((sum, b) => sum + b.total_spent, 0),
    activeUsers: balances.filter((b) => b.balance > 0).length,
  };

  return (
    <div className="w-full px-4 py-4">
      {/* Header */}
      <Flex justifyContent="between" alignItems="center" className="mb-4">
        <Title>Stripe Balance Management</Title>
        <Button
          icon={RefreshIcon}
          onClick={fetchBalances}
          loading={loading}
          variant="secondary"
        >
          Refresh
        </Button>
      </Flex>

      {/* Statistics Cards */}
      <Grid numItems={1} numItemsSm={2} numItemsLg={4} className="gap-4 mb-6">
        <Card>
          <Flex alignItems="start">
            <div className="truncate">
              <Text>Total Users</Text>
              <div className="mt-1">
                <Text className="text-2xl font-semibold text-tremor-content-strong">
                  {stats.totalUsers}
                </Text>
              </div>
            </div>
          </Flex>
        </Card>

        <Card>
          <Flex alignItems="start">
            <div className="truncate">
              <Text>Total Balance</Text>
              <div className="mt-1">
                <Text className="text-2xl font-semibold text-tremor-content-strong">
                  {formatCurrency(stats.totalBalance)}
                </Text>
              </div>
            </div>
          </Flex>
        </Card>

        <Card>
          <Flex alignItems="start">
            <div className="truncate">
              <Text>Total Top-ups</Text>
              <div className="mt-1">
                <Text className="text-2xl font-semibold text-tremor-content-strong">
                  {formatCurrency(stats.totalTopups)}
                </Text>
              </div>
            </div>
          </Flex>
        </Card>

        <Card>
          <Flex alignItems="start">
            <div className="truncate">
              <Text>Total Spent</Text>
              <div className="mt-1">
                <Text className="text-2xl font-semibold text-tremor-content-strong">
                  {formatCurrency(stats.totalSpent)}
                </Text>
              </div>
            </div>
          </Flex>
        </Card>
      </Grid>

      {/* Search and Filters */}
      <Card className="mb-4">
        <TextInput
          icon={SearchIcon}
          placeholder="Search by customer ID, type, or Stripe ID..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </Card>

      {/* Balances Table */}
      <Card>
        {loading ? (
          <div className="flex justify-center items-center py-8">
            <Spin size="large" />
          </div>
        ) : filteredBalances.length === 0 ? (
          <Alert
            message="No balance records found"
            description={
              balances.length === 0
                ? "No users have topped up their accounts yet."
                : "No results match your search criteria."
            }
            type="info"
            showIcon
          />
        ) : (
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Customer</TableHeaderCell>
                <TableHeaderCell>Type</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
                <TableHeaderCell className="text-right">Balance</TableHeaderCell>
                <TableHeaderCell className="text-right">Total Top-ups</TableHeaderCell>
                <TableHeaderCell className="text-right">Total Spent</TableHeaderCell>
                <TableHeaderCell>Last Updated</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredBalances.map((balance) => (
                <TableRow key={balance.id}>
                  <TableCell>
                    <Tooltip title={balance.stripe_customer_id}>
                      <Text className="font-mono">{balance.customer_id}</Text>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <Tag color="blue">{balance.customer_type}</Tag>
                  </TableCell>
                  <TableCell>
                    {getBalanceBadge(balance.balance, balance.low_balance_threshold)}
                  </TableCell>
                  <TableCell className="text-right">
                    <Text className="font-semibold">
                      {formatCurrency(balance.balance)}
                    </Text>
                  </TableCell>
                  <TableCell className="text-right">
                    <Text>{formatCurrency(balance.total_topups)}</Text>
                  </TableCell>
                  <TableCell className="text-right">
                    <Text>{formatCurrency(balance.total_spent)}</Text>
                  </TableCell>
                  <TableCell>
                    <Text className="text-xs">{formatDate(balance.updated_at)}</Text>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      {/* Info Banner */}
      {balances.length > 0 && (
        <Alert
          className="mt-4"
          message="Balance Management"
          description={
            <div>
              <p>This view shows all user prepaid balances in the system.</p>
              <ul className="list-disc ml-4 mt-2">
                <li>Balance is deducted automatically on each API request</li>
                <li>Users can top up via Stripe Checkout (see API documentation)</li>
                <li>Low balance warnings are logged when threshold is reached</li>
                <li>Transactions are recorded for audit purposes</li>
              </ul>
            </div>
          }
          type="info"
          showIcon
        />
      )}
    </div>
  );
};

export default StripeBalanceManagement;
