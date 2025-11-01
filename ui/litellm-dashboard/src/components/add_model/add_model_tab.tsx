import React, { useEffect, useMemo, useState } from "react";
import { Card, Form, Button, Tooltip, Typography, Select as AntdSelect, Modal, message } from "antd";
const { Title, Link } = Typography;
import type { FormInstance } from "antd";
import type { UploadProps } from "antd/es/upload";
import { TabGroup, TabList, Tab, TabPanels, TabPanel } from "@tremor/react";
import LiteLLMModelNameField from "./litellm_model_name";
import ConditionalPublicModelName from "./conditional_public_model_name";
import ProviderSpecificFields from "./provider_specific_fields";
import AdvancedSettings from "./advanced_settings";
import { Providers, providerLogoMap, getPlaceholder } from "../provider_info_helpers";
import type { Team } from "../key_team_helpers/key_list";
import { CredentialItem, getGuardrailsList, modelAvailableCall } from "../networking";
import ConnectionErrorDisplay from "./model_connection_test";
import { TEST_MODES } from "./add_model_modes";
import { Row, Col } from "antd";
import { Text, TextInput, Switch } from "@tremor/react";
import TeamDropdown from "../common_components/team_dropdown";
import { all_admin_roles } from "@/utils/roles";
import AddAutoRouterTab from "./add_auto_router_tab";
import { handleAddAutoRouterSubmit } from "./handle_add_auto_router_submit";

interface AddModelTabProps {
  form: FormInstance;
  handleOk: () => void;
  selectedProvider: Providers;
  setSelectedProvider: (provider: Providers) => void;
  providerModels: string[];
  setProviderModelsFn: (provider: Providers) => void;
  getPlaceholder: (provider: Providers) => string;
  uploadProps: UploadProps;
  showAdvancedSettings: boolean;
  setShowAdvancedSettings: (show: boolean) => void;
  teams: Team[] | null;
  credentials: CredentialItem[];
  accessToken: string;
  userRole: string;
  premiumUser: boolean;
}

const AddModelTab: React.FC<AddModelTabProps> = ({
  form,
  handleOk,
  selectedProvider,
  setSelectedProvider,
  providerModels,
  setProviderModelsFn,
  getPlaceholder,
  uploadProps,
  showAdvancedSettings,
  setShowAdvancedSettings,
  teams,
  credentials,
  accessToken,
  userRole,
  premiumUser,
}) => {
  const [autoRouterForm] = Form.useForm();
  const [testMode, setTestMode] = useState<string>("chat");
  const [isResultModalVisible, setIsResultModalVisible] = useState<boolean>(false);
  const [isTestingConnection, setIsTestingConnection] = useState<boolean>(false);
  const [guardrailsList, setGuardrailsList] = useState<string[]>([]);
  const [connectionTestId, setConnectionTestId] = useState<string>("");
  const [isTeamOnly, setIsTeamOnly] = useState<boolean>(false);
  const [modelAccessGroups, setModelAccessGroups] = useState<string[]>([]);
  React.useEffect(() => {
    const fetchGuardrails = async () => {
      try {
        const response = await getGuardrailsList(accessToken);
        const guardrailNames = response.guardrails.map((g: { guardrail_name: string }) => g.guardrail_name);
        setGuardrailsList(guardrailNames);
      } catch (error) {
        console.error("Failed to fetch guardrails:", error);
      }
    };
    fetchGuardrails();
  }, [accessToken]);
  React.useEffect(() => {
    const fetchModelAccessGroups = async () => {
      const response = await modelAvailableCall(accessToken, "", "", false, null, true, true);
      setModelAccessGroups(response["data"].map((model: any) => model["id"]));
    };
    fetchModelAccessGroups();
  }, [accessToken]);
  const isAdmin = all_admin_roles.includes(userRole);
  const handleAutoRouterOk = () => {
    autoRouterForm.validateFields().then((values) => {
      handleAddAutoRouterSubmit(values, accessToken, autoRouterForm, handleOk);
    }).catch((error) => {
      console.error("Validation failed:", error);
    });
  };
  const handleTestConnection = async () => {
    setIsTestingConnection(true);
    setConnectionTestId(`test-${Date.now()}`);
    setIsResultModalVisible(true);
  };
  return (
    <div>
      <TabGroup className="w-full">
        <TabList className="mb-4">
          <Tab>Add Model</Tab>
          <Tab>Add Auto Router</Tab>
        </TabList>
        <TabPanels>
          <TabPanel>
            <Title level={2}>Add Model</Title>
            <Card>
              <Form
                form={form}
                onFinish={(values) => {
                  handleOk();
                }}
                onFinishFailed={() => {}}
                labelCol={{ span: 10 }}
                wrapperCol={{ span: 16 }}
                labelAlign="left"
              >
                {/* ...existing code... */}
              </Form>
            </Card>
          </TabPanel>
          <TabPanel>
            <AddAutoRouterTab
              form={autoRouterForm}
              handleOk={handleAutoRouterOk}
              accessToken={accessToken}
              userRole={userRole}
            />
          </TabPanel>
        </TabPanels>
      </TabGroup>
      <Modal
        title="Connection Test Results"
        open={isResultModalVisible}
        onCancel={() => {
          setIsResultModalVisible(false);
          setIsTestingConnection(false);
        }}
        footer={[
          <Button key="close" onClick={() => {
            setIsResultModalVisible(false);
            setIsTestingConnection(false);
          }}>
            Close
          </Button>
        ]}
        width={700}
      >
        {isResultModalVisible && (
          <ConnectionErrorDisplay
            key={connectionTestId}
            formValues={form.getFieldsValue()}
            accessToken={accessToken}
            testMode={testMode}
            modelName={form.getFieldValue('model_name') || form.getFieldValue('model')}
            onClose={() => {
              setIsResultModalVisible(false);
              setIsTestingConnection(false);
            }}
            onTestComplete={() => setIsTestingConnection(false)}
          />
        )}
      </Modal>
    </div>
  );
};

export default AddModelTab;
// ...existing code...