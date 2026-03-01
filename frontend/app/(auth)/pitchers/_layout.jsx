import { Slot } from "expo-router";
import SubscriptionGate from "../../../src/components/SubscriptionGate";

export default function PitchersLayout() {
  return (
    <SubscriptionGate>
      <Slot />
    </SubscriptionGate>
  );
}
