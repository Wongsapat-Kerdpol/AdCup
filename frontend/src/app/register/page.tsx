import { ComingSoon } from "@/components/layout/coming-soon";

// TODO(Person 1)
export default function RegisterPage() {
  return (
    <ComingSoon
      owner="Person 1 — Auth"
      title="Create an account"
      todo={[
        "Role picker: Brand or Creator (?role= query param pre-selects it)",
        "Display name, email, password (+ confirm) with validation",
        "POST /api/auth/register -> useAuth().login(res)",
      ]}
    />
  );
}
