import { View, TextInput, Pressable, ActivityIndicator } from "react-native";
import Svg, { Path, Circle as SvgCircle } from "react-native-svg";

/**
 * Styled search input with loading spinner and clear button.
 *
 * @param {{ value: string, onChange: function, loading: boolean, placeholder: string }} props
 */
export default function SearchInput({ value, onChange, loading, placeholder }) {
  return (
    <View className="relative">
      <TextInput
        value={value}
        onChangeText={onChange}
        placeholder={placeholder}
        placeholderTextColor="#9ca3af"
        className="w-full rounded-md border border-gray-300 px-3 py-2 pr-10 text-sm text-gray-900"
        autoCapitalize="none"
        autoCorrect={false}
      />
      <View className="absolute inset-y-0 right-0 items-center justify-center pr-3">
        {loading && <ActivityIndicator size="small" color="#9ca3af" />}
        {!loading && value ? (
          <Pressable
            onPress={() => onChange("")}
            accessibilityLabel="Clear search"
            hitSlop={8}
          >
            <Svg width={16} height={16} viewBox="0 0 20 20" fill="#9ca3af">
              <Path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </Svg>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}
