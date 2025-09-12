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
  Switch,
  TabPanel,
  TabPanels,
  TabGroup,
  TabList,
  Tab,
  SelectItem,
  Icon,
  Badge,
  Flex,
} from "@tremor/react";

import {
  PencilAltIcon,
  TrashIcon,
  PlusIcon,
  ExclamationIcon,
  CheckCircleIcon,
  XCircleIcon,
  EyeIcon,
} from "@heroicons/react/outline";

import {
  Modal,
  Typography,
  Form,
  Input,
  Select,
  Button as Button2,
  message,
  Popconfirm,
  Spin,
  Alert,
  Steps,
} from "antd";

const { Title, Paragraph } = Typography;
const { Step } = Steps;

import { parseErrorMessage } from "./shared/errorUtils";

interface StripeMeterManagementProps {
  accessToken: string | null;
  userRole: string | null;
  userID: string | null;
  premiumUser: boolean;
}

interface StripeMeter {
  id: string;
  display_name: string;
  event_name: string;
  description?: string;
  customer_mapping: {
    event_payload_key: string;
  };
  default_aggregation: {
    formula: string;
  };
  created: number;
  updated: number;
  livemode: boolean;
  status: string;
}

interface StripeConnection {
  success: boolean;
  account_id?: string;
  account_name?: string;
  country?: string;
  currency?: string;
  charges_enabled?: boolean;
  livemode?: boolean;
}

const StripeMeterManagement: React.FC<StripeMeterManagementProps> = ({
  accessToken,
  userRole,
  userID,
  premiumUser,
}) => {
  // State management
  const [meters, setMeters] = useState<StripeMeter[]>([]);
  const [loading, setLoading] = useState(false);
  const [stripeApiKey, setStripeApiKey] = useState<string>("");
  const [stripeConnection, setStripeConnection] = useState<StripeConnection | null>(null);
  const [connectionTesting, setConnectionTesting] = useState(false);
  const [useEnvKeys, setUseEnvKeys] = useState<boolean>(true);

  // Modal states
  const [isCreateModalVisible, setIsCreateModalVisible] = useState(false);
  const [isEditModalVisible, setIsEditModalVisible] = useState(false);
  const [isViewModalVisible, setIsViewModalVisible] = useState(false);
  const [selectedMeter, setSelectedMeter] = useState<StripeMeter | null>(null);

  // Form instances
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  // Wizard state for creation
  const [createStep, setCreateStep] = useState(0);

  // Auto-test connection when component mounts if using env keys
  useEffect(() => {
    if (useEnvKeys && accessToken) {
      testStripeConnection();
    }
  }, [useEnvKeys, accessToken]);

  // API helper functions
  const apiCall = async (endpoint: string, method: string = "GET", data?: any) => {
    try {
      const url = `/api${endpoint}`;
      const config: RequestInit = {
        method,
        headers: {
          "Authorization": `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
      };

      if (data && method !== "GET") {
        config.body = JSON.stringify(data);
      }

      const response = await fetch(url, config);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error: any) {
      console.error(`API call failed: ${endpoint}`, error);
      throw error;
    }
  };

  // Modified API call that doesn't require stripe_api_key parameter when using env vars
  const stripeApiCall = async (endpoint: string, method: string = "GET", data?: any) => {
    try {
      let apiUrl = `/api${endpoint}`;
      
      // If not using environment keys, add the API key as a parameter
      if (!useEnvKeys && stripeApiKey) {
        const separator = endpoint.includes('?') ? '&' : '?';
        apiUrl += `${separator}stripe_api_key=${encodeURIComponent(stripeApiKey)}`;
      }
      
      const config: RequestInit = {
        method,
        headers: {
          "Authorization": `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
      };

      if (data && method !== "GET") {
        // If using env keys, don't include stripe_api_key in the body
        if (useEnvKeys && data.stripe_api_key) {
          const { stripe_api_key, ...dataWithoutKey } = data;
          config.body = JSON.stringify(dataWithoutKey);
        } else {
          config.body = JSON.stringify(data);
        }
      }

      const response = await fetch(apiUrl, config);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error: any) {
      console.error(`Stripe API call failed: ${endpoint}`, error);
      throw error;
    }
  };

  // Test Stripe connection
  const testStripeConnection = async () => {
    if (!useEnvKeys && !stripeApiKey.trim()) {
      message.warning("Please enter a Stripe API key");
      return;
    }

    setConnectionTesting(true);
    try {
      const result = await stripeApiCall("/stripe/meters/test-connection", "POST");
      setStripeConnection(result);
      message.success("Stripe connection successful!");
      loadMeters();
    } catch (error: any) {
      message.error(`Connection failed: ${parseErrorMessage(error)}`);
      setStripeConnection(null);
    } finally {
      setConnectionTesting(false);
    }
  };

  // Load meters from Stripe
  const loadMeters = async () => {
    if (!useEnvKeys && !stripeApiKey.trim()) {
      return;
    }

    setLoading(true);
    try {
      const result = await stripeApiCall("/stripe/meters?limit=50");
      setMeters(result.meters || []);
    } catch (error: any) {
      message.error(`Failed to load meters: ${parseErrorMessage(error)}`);
      setMeters([]);
    } finally {
      setLoading(false);
    }
  };

  // Create a new meter
  const createMeter = async (values: any) => {
    try {
      const meterData = {
        display_name: values.display_name,
        event_name: values.event_name,
        description: values.description,
        customer_mapping_key: values.customer_mapping_key || "customer_id",
        aggregation_formula: values.aggregation_formula || "sum",
      };

      // Only add stripe_api_key if not using environment variables
      if (!useEnvKeys) {
        meterData.stripe_api_key = stripeApiKey;
      }

      const newMeter = await stripeApiCall("/stripe/meters", "POST", meterData);
      setMeters(prev => [...prev, newMeter]);
      setIsCreateModalVisible(false);
      setCreateStep(0);
      createForm.resetFields();
      message.success("Meter created successfully!");
    } catch (error: any) {
      message.error(`Failed to create meter: ${parseErrorMessage(error)}`);
    }
  };

  // Update an existing meter
  const updateMeter = async (values: any) => {
    if (!selectedMeter) return;

    try {
      const updateData = {
        display_name: values.display_name,
        description: values.description,
      };

      // Only add stripe_api_key if not using environment variables
      if (!useEnvKeys) {
        updateData.stripe_api_key = stripeApiKey;
      }

      const updatedMeter = await stripeApiCall(
        `/stripe/meters/${selectedMeter.id}`,
        "PATCH",
        updateData
      );

      setMeters(prev =>
        prev.map(meter => (meter.id === selectedMeter.id ? updatedMeter : meter))
      );
      setIsEditModalVisible(false);
      setSelectedMeter(null);
      editForm.resetFields();
      message.success("Meter updated successfully!");
    } catch (error: any) {
      message.error(`Failed to update meter: ${parseErrorMessage(error)}`);
    }
  };

  // Deactivate a meter
  const deactivateMeter = async (meter: StripeMeter) => {
    try {
      const deactivatedMeter = await stripeApiCall(
        `/stripe/meters/${meter.id}/deactivate`,
        "DELETE"
      );

      setMeters(prev =>
        prev.map(m => (m.id === meter.id ? deactivatedMeter : m))
      );
      message.success("Meter deactivated successfully!");
    } catch (error: any) {
      message.error(`Failed to deactivate meter: ${parseErrorMessage(error)}`);
    }
  };

  // Open edit modal
  const openEditModal = (meter: StripeMeter) => {
    setSelectedMeter(meter);
    editForm.setFieldsValue({
      display_name: meter.display_name,
      description: meter.description,
    });
    setIsEditModalVisible(true);
  };

  // Open view modal
  const openViewModal = (meter: StripeMeter) => {
    setSelectedMeter(meter);
    setIsViewModalVisible(true);
  };

  // Render connection status
  const renderConnectionStatus = () => {
    if (!stripeConnection) return null;

    return (
      <Alert
        type="success"
        message="Stripe Connection Active"
        description={
          <div>
            <p><strong>Account:</strong> {stripeConnection.account_name || stripeConnection.account_id}</p>
            <p><strong>Country:</strong> {stripeConnection.country}</p>
            <p><strong>Currency:</strong> {stripeConnection.currency?.toUpperCase()}</p>
            <p><strong>Mode:</strong> {stripeConnection.livemode ? "Live" : "Test"}</p>
            <p><strong>Charges Enabled:</strong> {stripeConnection.charges_enabled ? "Yes" : "No"}</p>
          </div>
        }
        showIcon
        style={{ marginBottom: 16 }}
      />
    );
  };

  // Render meter status badge
  const renderStatus = (status: string) => {
    const isActive = status === "active";
    return (
      <Badge
        color={isActive ? "green" : "red"}
        icon={isActive ? CheckCircleIcon : XCircleIcon}
      >
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    );
  };

  // Format date
  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleDateString();
  };

  // Create wizard steps
  const createSteps = [
    {
      title: "Basic Info",
      content: (
        <div className="space-y-4">
          <Form.Item
            label="Display Name"
            name="display_name"
            rules={[{ required: true, message: "Please enter a display name" }]}
          >
            <Input placeholder="e.g., LiteLLM Token Usage" />
          </Form.Item>
          <Form.Item
            label="Event Name"
            name="event_name"
            rules={[
              { required: true, message: "Please enter an event name" },
              { pattern: /^[a-zA-Z0-9_-]+$/, message: "Only letters, numbers, underscores, and hyphens allowed" }
            ]}
          >
            <Input placeholder="e.g., litellm_token_usage" />
          </Form.Item>
          <Form.Item
            label="Description"
            name="description"
          >
            <Input.TextArea placeholder="Optional description of what this meter tracks" rows={3} />
          </Form.Item>
        </div>
      ),
    },
    {
      title: "Configuration",
      content: (
        <div className="space-y-4">
          <Form.Item
            label="Customer Mapping Key"
            name="customer_mapping_key"
            initialValue="customer_id"
          >
            <Select>
              <Select.Option value="customer_id">customer_id</Select.Option>
              <Select.Option value="user_id">user_id</Select.Option>
              <Select.Option value="end_user_id">end_user_id</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item
            label="Aggregation Formula"
            name="aggregation_formula"
            initialValue="sum"
          >
            <Select>
              <Select.Option value="sum">Sum</Select.Option>
              <Select.Option value="count">Count</Select.Option>
            </Select>
          </Form.Item>
          <Alert
            type="info"
            message="Configuration Note"
            description="These settings determine how usage events are aggregated and which field identifies customers in your events."
            showIcon
          />
        </div>
      ),
    },
    {
      title: "Review",
      content: (
        <div className="space-y-4">
          <Alert
            type="success"
            message="Ready to Create"
            description="Review your meter configuration below and click 'Create Meter' to proceed."
            showIcon
          />
          <div className="bg-gray-50 p-4 rounded">
            <h4>Meter Summary</h4>
            <p><strong>Display Name:</strong> {createForm.getFieldValue("display_name")}</p>
            <p><strong>Event Name:</strong> {createForm.getFieldValue("event_name")}</p>
            <p><strong>Description:</strong> {createForm.getFieldValue("description") || "None"}</p>
            <p><strong>Customer Mapping:</strong> {createForm.getFieldValue("customer_mapping_key")}</p>
            <p><strong>Aggregation:</strong> {createForm.getFieldValue("aggregation_formula")}</p>
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="w-full mx-auto">
      <Card>
        <Title level={2}>Stripe Meter Management</Title>
        <Paragraph>
          Create and manage Stripe meters for usage-based billing. Meters track usage events and aggregate them for billing purposes.
        </Paragraph>

        {/* Stripe API Key Configuration */}
        <Card className="mb-4">
          <Title level={4}>Stripe Configuration</Title>
          
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-2">
              <Switch
                checked={useEnvKeys}
                onChange={(checked) => {
                  setUseEnvKeys(checked);
                  setStripeConnection(null);
                  setMeters([]);
                }}
              />
              <Text>Use Environment Variables (STRIPE_SECRET)</Text>
            </div>
            {useEnvKeys && (
              <Alert
                type="info"
                message="Using Environment Configuration"
                description="Stripe API keys are configured via environment variables. No manual key entry required."
                showIcon
                className="mb-4"
              />
            )}
          </div>

          {!useEnvKeys && (
            <div className="flex gap-4 items-end mb-4">
              <div className="flex-1">
                <Text>Stripe API Key</Text>
                <TextInput
                  placeholder="sk_test_... or sk_live_..."
                  value={stripeApiKey}
                  onChange={(e) => setStripeApiKey(e.target.value)}
                  type="password"
                />
              </div>
            </div>
          )}

          <div className="flex gap-2">
            <Button
              onClick={testStripeConnection}
              loading={connectionTesting}
              disabled={!useEnvKeys && !stripeApiKey.trim()}
            >
              Test Connection
            </Button>
            {stripeConnection && (
              <Button
                onClick={loadMeters}
                loading={loading}
              >
                Reload Meters
              </Button>
            )}
          </div>
          
          {renderConnectionStatus()}
        </Card>

        {/* Meters Table */}
        <Card>
          <div className="flex justify-between items-center mb-4">
            <Title level={4}>Meters</Title>
            <Button
              icon={PlusIcon}
              onClick={() => setIsCreateModalVisible(true)}
              disabled={!stripeConnection}
            >
              Create Meter
            </Button>
          </div>

          {loading ? (
            <div className="text-center p-8">
              <Spin size="large" />
              <p className="mt-4">Loading meters...</p>
            </div>
          ) : (
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Display Name</TableHeaderCell>
                  <TableHeaderCell>Event Name</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell>Created</TableHeaderCell>
                  <TableHeaderCell>Actions</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {meters.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8">
                      <div className="text-gray-500">
                        {stripeConnection ? "No meters found" : "Connect to Stripe to view meters"}
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  meters.map((meter) => (
                    <TableRow key={meter.id}>
                      <TableCell>
                        <Text className="font-medium">{meter.display_name}</Text>
                        {meter.description && (
                          <Text className="text-gray-500 text-sm">{meter.description}</Text>
                        )}
                      </TableCell>
                      <TableCell>
                        <code className="bg-gray-100 px-2 py-1 rounded text-sm">
                          {meter.event_name}
                        </code>
                      </TableCell>
                      <TableCell>{renderStatus(meter.status)}</TableCell>
                      <TableCell>{formatDate(meter.created)}</TableCell>
                      <TableCell>
                        <Flex className="gap-2">
                          <Button
                            size="xs"
                            variant="light"
                            icon={EyeIcon}
                            onClick={() => openViewModal(meter)}
                          />
                          <Button
                            size="xs"
                            variant="light"
                            icon={PencilAltIcon}
                            onClick={() => openEditModal(meter)}
                            disabled={meter.status !== "active"}
                          />
                          <Popconfirm
                            title="Deactivate Meter"
                            description="Are you sure you want to deactivate this meter? This action cannot be undone."
                            onConfirm={() => deactivateMeter(meter)}
                            disabled={meter.status !== "active"}
                          >
                            <Button
                              size="xs"
                              variant="light"
                              icon={TrashIcon}
                              color="red"
                              disabled={meter.status !== "active"}
                            />
                          </Popconfirm>
                        </Flex>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
        </Card>

        {/* Create Meter Modal */}
        <Modal
          title="Create Stripe Meter"
          open={isCreateModalVisible}
          onCancel={() => {
            setIsCreateModalVisible(false);
            setCreateStep(0);
            createForm.resetFields();
          }}
          footer={null}
          width={600}
        >
          <Steps current={createStep} className="mb-6">
            {createSteps.map((step, index) => (
              <Step key={index} title={step.title} />
            ))}
          </Steps>

          <Form
            form={createForm}
            layout="vertical"
            onFinish={createMeter}
          >
            {createSteps[createStep].content}

            <div className="flex justify-between mt-6">
              <Button
                onClick={() => setCreateStep(Math.max(0, createStep - 1))}
                disabled={createStep === 0}
              >
                Previous
              </Button>
              
              {createStep < createSteps.length - 1 ? (
                <Button2
                  type="primary"
                  onClick={() => {
                    createForm.validateFields().then(() => {
                      setCreateStep(createStep + 1);
                    });
                  }}
                >
                  Next
                </Button2>
              ) : (
                <Button2 type="primary" htmlType="submit">
                  Create Meter
                </Button2>
              )}
            </div>
          </Form>
        </Modal>

        {/* Edit Meter Modal */}
        <Modal
          title="Edit Stripe Meter"
          open={isEditModalVisible}
          onCancel={() => {
            setIsEditModalVisible(false);
            setSelectedMeter(null);
            editForm.resetFields();
          }}
          footer={null}
        >
          <Form
            form={editForm}
            layout="vertical"
            onFinish={updateMeter}
          >
            <Form.Item
              label="Display Name"
              name="display_name"
              rules={[{ required: true, message: "Please enter a display name" }]}
            >
              <Input />
            </Form.Item>
            <Form.Item
              label="Description"
              name="description"
            >
              <Input.TextArea rows={3} />
            </Form.Item>

            <div className="flex justify-end gap-2 mt-6">
              <Button2
                onClick={() => {
                  setIsEditModalVisible(false);
                  setSelectedMeter(null);
                  editForm.resetFields();
                }}
              >
                Cancel
              </Button2>
              <Button2 type="primary" htmlType="submit">
                Update Meter
              </Button2>
            </div>
          </Form>
        </Modal>

        {/* View Meter Modal */}
        <Modal
          title="Meter Details"
          open={isViewModalVisible}
          onCancel={() => {
            setIsViewModalVisible(false);
            setSelectedMeter(null);
          }}
          footer={[
            <Button2
              key="close"
              onClick={() => {
                setIsViewModalVisible(false);
                setSelectedMeter(null);
              }}
            >
              Close
            </Button2>
          ]}
        >
          {selectedMeter && (
            <div className="space-y-4">
              <div>
                <Text className="font-medium">Display Name:</Text>
                <p>{selectedMeter.display_name}</p>
              </div>
              <div>
                <Text className="font-medium">Event Name:</Text>
                <p><code className="bg-gray-100 px-2 py-1 rounded">{selectedMeter.event_name}</code></p>
              </div>
              <div>
                <Text className="font-medium">Description:</Text>
                <p>{selectedMeter.description || "No description provided"}</p>
              </div>
              <div>
                <Text className="font-medium">Status:</Text>
                <p>{renderStatus(selectedMeter.status)}</p>
              </div>
              <div>
                <Text className="font-medium">Customer Mapping:</Text>
                <p>{selectedMeter.customer_mapping.event_payload_key}</p>
              </div>
              <div>
                <Text className="font-medium">Aggregation Formula:</Text>
                <p>{selectedMeter.default_aggregation.formula}</p>
              </div>
              <div>
                <Text className="font-medium">Created:</Text>
                <p>{formatDate(selectedMeter.created)}</p>
              </div>
              <div>
                <Text className="font-medium">Last Updated:</Text>
                <p>{formatDate(selectedMeter.updated)}</p>
              </div>
              <div>
                <Text className="font-medium">Mode:</Text>
                <p>{selectedMeter.livemode ? "Live" : "Test"}</p>
              </div>
              <div>
                <Text className="font-medium">Meter ID:</Text>
                <p><code className="bg-gray-100 px-2 py-1 rounded">{selectedMeter.id}</code></p>
              </div>
            </div>
          )}
        </Modal>
      </Card>
    </div>
  );
};

export default StripeMeterManagement;