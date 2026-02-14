import { gql } from '@apollo/client'

export const LOGIN = gql`
  mutation Login($email: String!, $password: String!) {
    login(email: $email, password: $password) {
      token
      user {
        id
        email
        fullName
        role
        orgId
      }
    }
  }
`

export const GET_ME = gql`
  query Me {
    me {
      id
      email
      fullName
      role
      orgId
    }
  }
`

export const GET_USERS = gql`
  query Users {
    users {
      id
      email
      fullName
      role
    }
  }
`

export const GET_PURCHASE_REQUESTS = gql`
  query PurchaseRequests($page: Int, $pageSize: Int, $status: String, $category: String) {
    purchaseRequests(page: $page, pageSize: $pageSize, status: $status, category: $category) {
      items {
        id
        title
        vendor
        amount
        category
        costCenter
        status
        requester {
          fullName
        }
        createdAt
        submittedAt
        approvedAt
        rejectedAt
      }
      total
      page
      pageSize
    }
  }
`

export const GET_PURCHASE_REQUEST = gql`
  query PurchaseRequest($id: ID!) {
    purchaseRequest(id: $id) {
      id
      title
      description
      vendor
      amount
      category
      costCenter
      status
      requesterId
      requester {
        fullName
        email
      }
      approvalSteps {
        id
        stepOrder
        status
        approver {
          fullName
          email
        }
        policy {
          name
        }
        decision {
          decision
          comments
          decider {
            fullName
          }
          decidedAt
        }
        createdAt
      }
      createdAt
      updatedAt
      submittedAt
      approvedAt
      rejectedAt
    }
  }
`

export const CREATE_PURCHASE_REQUEST = gql`
  mutation CreatePurchaseRequest($input: CreateRequestInput!) {
    createPurchaseRequest(input: $input) {
      id
      title
      status
    }
  }
`

export const UPDATE_PURCHASE_REQUEST = gql`
  mutation UpdatePurchaseRequest($id: ID!, $input: UpdateRequestInput!) {
    updatePurchaseRequest(id: $id, input: $input) {
      id
      title
      status
    }
  }
`

export const SUBMIT_REQUEST = gql`
  mutation SubmitRequest($id: ID!) {
    submitRequest(id: $id) {
      id
      status
    }
  }
`

export const CANCEL_REQUEST = gql`
  mutation CancelRequest($id: ID!) {
    cancelRequest(id: $id) {
      id
      status
    }
  }
`

export const GET_APPROVAL_INBOX = gql`
  query ApprovalInbox {
    approvalInbox {
      id
      stepOrder
      status
      approver {
        fullName
      }
      policy {
        name
      }
      purchaseRequest {
        id
        title
        vendor
        amount
        category
        costCenter
        status
        requester {
          fullName
        }
        createdAt
      }
      createdAt
    }
  }
`

export const APPROVE_STEP = gql`
  mutation ApproveStep($stepId: ID!, $comments: String) {
    approveStep(stepId: $stepId, comments: $comments) {
      id
      status
    }
  }
`

export const REJECT_STEP = gql`
  mutation RejectStep($stepId: ID!, $comments: String) {
    rejectStep(stepId: $stepId, comments: $comments) {
      id
      status
    }
  }
`

export const GET_APPROVAL_POLICIES = gql`
  query ApprovalPolicies {
    approvalPolicies {
      id
      name
      description
      approverId
      approver {
        fullName
      }
      priority
      isActive
      rules {
        id
        field
        operator
        value
      }
    }
  }
`

export const CREATE_APPROVAL_POLICY = gql`
  mutation CreateApprovalPolicy($input: CreatePolicyInput!) {
    createApprovalPolicy(input: $input) {
      id
      name
    }
  }
`

export const UPDATE_APPROVAL_POLICY = gql`
  mutation UpdateApprovalPolicy($id: ID!, $input: UpdatePolicyInput!) {
    updateApprovalPolicy(id: $id, input: $input) {
      id
      name
    }
  }
`

export const DELETE_APPROVAL_POLICY = gql`
  mutation DeleteApprovalPolicy($id: ID!) {
    deleteApprovalPolicy(id: $id)
  }
`

export const GET_AUDIT_LOGS = gql`
  query AuditLogs($entityId: ID, $page: Int, $pageSize: Int) {
    auditLogs(entityId: $entityId, page: $page, pageSize: $pageSize) {
      items {
        id
        entityType
        entityId
        action
        oldValue
        newValue
        performer {
          fullName
        }
        createdAt
      }
      total
      page
      pageSize
    }
  }
`

export const GET_CYCLE_TIME_REPORT = gql`
  query CycleTimeReport {
    cycleTimeReport {
      status
      avgHours
      count
    }
  }
`

export const GET_CATEGORY_REPORT = gql`
  query CategoryReport {
    categoryReport {
      category
      count
      totalAmount
    }
  }
`

export const GET_BOTTLENECK_REPORT = gql`
  query BottleneckReport {
    bottleneckReport {
      approverName
      approverId
      pendingCount
      avgDecisionHours
    }
  }
`
